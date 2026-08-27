"""Render dashboard pages and actions."""

import csv
import logging

from botocore.exceptions import BotoCoreError, ClientError
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Max
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from apps.sample_catalog import ocs_sync as sync
from apps.sample_catalog.models import NOT_COMPLETED, BatchPrefix, Sample, Stage, StageStatus
from apps.submission_queue.models import CartItem
from apps.web_ui import columns
from apps.web_ui.forms import SyncForm
from apps.workflow_engine import modality
from apps.workflow_engine.models import WorkflowConfig

from .common import (
    DEFAULT_SORT,
    FILTER_FIELDS,
    PAGE_SIZE_OPTIONS,
    SORTABLE,
    _batch_options,
    _Echo,
    _filtered_samples,
    _page_size,
    _prefix_counts,
    _safe_next,
    _scoped_distinct,
    _scoped_statuses,
    _sorted,
    _status_sync_context,
    _study_options,
)

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """List fastq samples and start a submission."""
    return render(request, "dashboard.html", _dashboard_context(request))


@login_required
@require_POST
def sync_samples(request):
    form = SyncForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a batch name to sync.")
        return redirect("web_ui:dashboard")

    batch = form.cleaned_data["batch_name_from_vendor"]
    try:
        synced = sync.sync_batch(batch)
    except (BotoCoreError, ClientError) as error:
        logger.warning("Batch sync failed for %s: %s", batch, error)
        messages.error(request, "Could not reach OCS. Nothing was synced.")
        return redirect("web_ui:dashboard")

    if synced:
        messages.success(request, f"Synced {len(synced)} samples from {batch}.")
    else:
        messages.warning(request, f"OCS returned no samples for {batch}.")

    query = urlencode({"batch_name_from_vendor": batch})
    return redirect(f"{reverse('web_ui:dashboard')}?{query}")


@login_required
@require_POST
def refresh_status(request):
    """Refresh the visible fastq samples' stage status from OCS."""
    # The POST body contains the rows currently shown. Deduplicate names before querying
    # and counting them.
    fastq_names = list(dict.fromkeys(request.POST.getlist("fastq_names")))
    samples = list(Sample.objects.filter(fastq_name__in=fastq_names))
    if not samples:
        messages.error(request, "No samples to refresh.")
        return redirect(_safe_next(request))

    try:
        sync.sync_stage_statuses(samples)
    except (BotoCoreError, ClientError) as error:
        # The mirror is still there and still readable; only this refresh failed.
        logger.warning("Live status refresh failed: %s", error)
        messages.error(request, "Could not reach OCS. The table still shows the last sweep.")
    else:
        label = "sample" if len(samples) == 1 else "samples"
        messages.success(request, f"Refreshed status for {len(samples)} {label} from OCS.")

    return redirect(_safe_next(request))


@login_required
def live_status(request):
    """Return current database status for the visible fastq samples."""
    fastq_names = request.GET.getlist("fastq_names")
    if not fastq_names or len(fastq_names) > PAGE_SIZE_OPTIONS[-1]:
        return JsonResponse({"rows": {}})

    records = StageStatus.objects.filter(sample__fastq_name__in=fastq_names).values(
        "sample__fastq_name", "stage", "status"
    )
    rows: dict[str, dict[str, dict[str, str]]] = {}
    for record in records:
        rows.setdefault(record["sample__fastq_name"], {})[record["stage"]] = {
            "status": record["status"],
        }
    return JsonResponse({"rows": rows})


@login_required
@require_POST
def set_columns(request):
    """Save the dashboard columns selected by the user."""
    scope = request.POST.get("scope", "samples")
    allowed = columns.LOCATION_COLUMN_KEYS if scope == "locations" else columns.COLUMNS_BY_KEY
    chosen = [key for key in request.POST.getlist("columns") if key in allowed]
    if scope == "locations":
        request.user.visible_location_columns = chosen
        request.user.save(update_fields=["visible_location_columns"])
    else:
        # Keep fastq_name visible because it identifies each row.
        request.user.visible_columns = ["fastq_name", *[key for key in chosen if key != "fastq_name"]]
        request.user.save(update_fields=["visible_columns"])
    return redirect(_safe_next(request))


@login_required
@require_POST
def export_csv(request):
    """Return the current fastq sample selection as CSV.

    Streams, and iterates the queryset in chunks, because this is pointed at the whole
    mirror: buffering hundreds of thousands of rows into one response is how an export
    endpoint takes the web worker down with it.

    Exports the columns the user has chosen, so the file matches the table they are
    looking at rather than some other idea of what a sample is.
    """
    chosen = request.POST.getlist("fastq_names")
    samples = _filtered_samples(request)
    if chosen:
        # A selected row takes precedence over the filters. Otherwise the export includes
        # every filtered row.
        samples = samples.filter(fastq_name__in=chosen)

    visible = columns.visible_columns(request.user)
    writer = csv.writer(_Echo())

    def rows():
        yield writer.writerow([column.label for column in visible])
        for sample in samples.iterator(chunk_size=2000):
            yield writer.writerow([_export_value(sample, column) for column in visible])

    filename = "omicshub-samples.csv"
    response = StreamingHttpResponse(rows(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _export_value(sample, column):
    """Return one cell as spreadsheet text.

    A leading "=", "+", "-" or "@" is treated as a formula by Excel, so those are prefixed
    to stop a vendor batch name executing when the file is opened.
    """
    value = column.value_for(sample, raw=True)
    text = "" if value is None else str(value)
    return f"'{text}" if text[:1] in ("=", "+", "-", "@") else text


@login_required
@require_POST
def cart_add(request):
    """Add the selected dashboard samples to checkout.

    Idempotent: adding a sample already in the cart is a no-op rather than an error, so a
    user who ticks overlapping selections across two pages ends up with one of each.
    """
    fastq_names = request.POST.getlist("fastq_names")
    if not fastq_names:
        return _cart_add_result(request, error="Select at least one sample to add to the cart.", status=400)

    samples = list(Sample.objects.filter(fastq_name__in=fastq_names))
    in_cart = _cart_sample_ids(request.user, samples)

    # `ignore_conflicts` rather than trusting the read above. Between that query and this
    # A concurrent insert can trigger the unique constraint, so use ignore_conflicts to make
    # the operation idempotent.
    CartItem.objects.bulk_create(
        [CartItem(user=request.user, sample=sample) for sample in samples if sample.pk not in in_cart],
        ignore_conflicts=True,
    )

    # Count rows stored in the database, not rows passed to bulk_create. With ignore_conflicts,
    # the input list can include rows that already exist.
    added = len(_cart_sample_ids(request.user, samples)) - len(in_cart)
    return _cart_add_result(
        request,
        added=added,
        already=len(in_cart),
        # If a sample disappeared during a resync, count it as missing so the response
        # explains why it was not added.
        missing=len(fastq_names) - len(samples),
    )


def _cart_sample_ids(user, samples) -> set[int]:
    return set(CartItem.objects.filter(user=user, sample__in=samples).values_list("sample_id", flat=True))


def _cart_add_result(request, *, added=0, already=0, missing=0, error="", status=200):
    """Return a cart-add result as dashboard JSON or a redirect.

        The dashboard adds without leaving the page, because the confirmation belongs where the
        action is: the button sits at the bottom of a table that scrolls inside its own box, so
        a message banner at the top of the document lands the better part of a screen away from
        where the user is looking, and reads as nothing having happened.

    The redirect is what happens with JavaScript off, and the tests exercise it because
        same counts, same wording, carried as messages instead.
    """
    parts = []
    if added:
        parts.append(f"Added {added} sample{'s' if added != 1 else ''} to the cart.")
    if already:
        parts.append(f"{already} already in the cart.")
    if missing:
        parts.append(f"{missing} no longer in the mirror.")
    if not parts and not error:
        parts.append("Nothing to add.")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "error": error,
                "message": error or " ".join(parts),
                "added": added,
                "already": already,
                "missing": missing,
                "cart_count": CartItem.objects.filter(user=request.user).count(),
            },
            status=status,
        )

    if error:
        messages.error(request, error)
    else:
        if added:
            messages.success(request, parts[0])
        for part in parts[1 if added else 0 :]:
            messages.info(request, part)
    return redirect(_safe_next(request))


@login_required
@require_POST
def cart_remove(request):
    """Remove fastq samples from the cart."""
    fastq_names = request.POST.getlist("fastq_names")
    removed, _ = CartItem.objects.filter(user=request.user, sample__fastq_name__in=fastq_names).delete()
    if removed:
        messages.success(request, f"Removed {removed} sample{'s' if removed != 1 else ''} from the cart.")
    return redirect("web_ui:checkout")


@login_required
@require_POST
def cart_clear(request):
    CartItem.objects.filter(user=request.user).delete()
    messages.success(request, "Cart emptied.")
    return redirect("web_ui:checkout")


def _dashboard_context(request):
    queryset = _sorted(_filtered_samples(request), request)
    stage_filters = [
        {"stage": stage, "selected": request.GET.get(f"{stage.value}_status", "")} for stage in Stage
    ]

    metadata_synced_at = Sample.objects.aggregate(at=Max("synced_at"))["at"]

    # The tab, and only the tab. The advanced-filter menus are built from this rather than
    # the whole mirror so they offer values that can return rows, and rather than
    # from the fully-filtered queryset so choosing an organism does not empty the batch menu.
    prefix = request.GET.get("batch_prefix")
    scope = Sample.objects.all()
    if prefix in BatchPrefix.values:
        scope = scope.filter(batch_prefix=prefix)

    config = WorkflowConfig.objects.filter(is_active=True).first()
    page_size = _page_size(request)
    page = Paginator(queryset, page_size).get_page(request.GET.get("page"))

    return {
        "page": page,
        "page_size": page_size,
        "page_size_options": PAGE_SIZE_OPTIONS,
        "sync_form": SyncForm(),
        "stages": Stage,
        "columns": columns.visible_columns(request.user),
        "all_columns": columns.COLUMNS,
        "column_groups": columns.COLUMN_GROUPS,
        "locked_column": columns.LOCKED_COLUMN,
        # The chooser's "Restore defaults" needs to know what the defaults are without a
        # round trip, so it ships with the page rather than being fetched on click.
        "default_column_keys": columns.DEFAULT_COLUMNS,
        "visible_column_keys": request.user.visible_columns or columns.DEFAULT_COLUMNS,
        "search": request.GET.get("fastq_name") or "",
        "filters": {field: request.GET.getlist(field) for field in FILTER_FIELDS},
        "stage_filters": stage_filters,
        # Which column the table is ordered by, so the header can show the arrow.
        "sort": request.GET.get("sort") if request.GET.get("sort") in SORTABLE else DEFAULT_SORT,
        "dir": "asc" if request.GET.get("dir") == "asc" else "desc",
        "sortable_keys": list(SORTABLE),
        # How often the two sweeps run, for the freshness clock tooltip. Otherwise
        # "3 minutes old" does not distinguish stale data from a sweep that is not yet due.
        "metadata_refresh": "nightly at 03:00",
        **_status_sync_context(),
        "batch_prefixes": _prefix_counts(),
        "selected_prefix": request.GET.get("batch_prefix", ""),
        "studies": _study_options(),
        "selected_studies": request.GET.getlist("study"),
        "modalities": modality.available_modalities(config.data) if config else [],
        # Filter options come from the mirror, so a dropdown never
        # offers a value that would return nothing. That is what keeps the batch menu
        # short: OCS has nearly two thousand batches, the mirror only the synced ones.
        # Scoped to the selected tab. On the MTX tab the batch menu lists MTX batches and
        # nothing else. Offering RTX batches there produces a filter combination that can
        # only ever return an empty table.
        "batches": _batch_options(request.GET.getlist("batch_name_from_vendor"), scope),
        "organisms": _scoped_distinct(scope, "organism_common_name"),
        "library_preps": _scoped_distinct(scope, "library_prep_method_name"),
        "statuses": [NOT_COMPLETED, *_scoped_statuses(scope)],
        "filters_open": any(request.GET.getlist(field) for field in FILTER_FIELDS)
        or any(row["selected"] for row in stage_filters),
        # Show the active-filter count on the collapsed panel button so users can see the
        # current filter state without opening the panel.
        "active_filter_count": sum(1 for field in FILTER_FIELDS if request.GET.getlist(field))
        + sum(1 for row in stage_filters if row["selected"]),
        # Display the mirror's synchronization timestamp in the header.
        "metadata_synced_at": metadata_synced_at,
    }
