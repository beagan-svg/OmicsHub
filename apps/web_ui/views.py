"""Render the server-side pages for samples, checkout, and queue entries.

Dashboard → cart → checkout → submit modal → confirmation modal → confirm, plus queue,
job monitor and failed-jobs pages. The modals are rendered on the server and opened on
load, so the multi-step flow needs no client-side state: each step is a POST that carries
the previous step's choices forward.

These views delegate planning, queue creation, and OCS synchronization to the owning app modules.
which is what keeps the pages and the API from drifting apart. In particular the checkout
page decides nothing about *what* to run: the selected config does, through
`planning.build_plan`, which is the same call the API makes.
"""

import csv
import io
import logging
import re
import zipfile
from collections import deque
from collections.abc import Buffer, Iterator, Sequence
from functools import wraps

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import BigIntegerField, Count, Exists, F, Func, Max, OuterRef, Q, Value
from django.db.models.functions import Cast, NullIf
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import require_GET, require_POST

from apps.ocs_integration import dynamodb, s3
from apps.sample_catalog import multiome_pairing as pairing
from apps.sample_catalog import ocs_sync as sync
from apps.sample_catalog.models import MULTIOME_PREPS, NOT_COMPLETED, BatchPrefix, Sample, Stage, StageStatus
from apps.submission_queue import queue_entries as enqueue_service
from apps.submission_queue import queue_planning as planning
from apps.submission_queue import tasks
from apps.submission_queue.models import CartItem, QueueEntry
from apps.web_ui import columns
from apps.web_ui import data_location_queries as locations
from apps.web_ui.forms import ConfigUploadForm, SubmissionForm, SyncForm
from apps.workflow_engine import command_builder, manifest_service, modality
from apps.workflow_engine.models import WorkflowConfig

logger = logging.getLogger(__name__)

FILTER_FIELDS = ("batch_name_from_vendor", "organism_common_name", "library_prep_method_name")
PAGE_SIZE = 50
PAGE_SIZE_OPTIONS = (25, 50, 100, 200)
DOWNLOAD_SELECTION_LIMIT = 1000

# The family tabs read in this order, which is not the order the model declares them in:
# declaration order answers to the data, this is a reading order.
TAB_ORDER = (BatchPrefix.RTX, BatchPrefix.RFX, BatchPrefix.MTX, BatchPrefix.ATX)

QUEUED_STATUSES = [QueueEntry.Status.PENDING, QueueEntry.Status.SUBMITTING]
FAILED_STATUSES = [QueueEntry.Status.FAILED]

# OCS's own labels, as they arrive in the mirror. The monitor reads these rather than queue
# statuses so it covers demands this app never submitted. AWAITING_TRIGGER and PENDING are
# running rather than finished: OCS has the job and has not started it, which is still work
# in flight from anyone watching the pipeline.
RUNNING_OCS_STATUSES = ("IN_PROGRESS", "SUBMITTED", "SUBMITTING", "PENDING", "AWAITING_TRIGGER")
FINISHED_OCS_STATUSES = ("COMPLETED", "ARCHIVED", "FAILED", "ABORTED", "STRANDED", "ABANDONED")

# The mirror holds every stage OCS has run for half a million samples. The monitor shows
# the most recent, and says so on the page rather than implying it is the whole picture.
MONITOR_ROWS = 200

# What the submit modal may change about one planned command. `probe_set` is here because a
# library prep the config does not list has no probe set to look up, and the modal asks for
# one rather than letting the flag ship empty. `command_original` is not an override: it is
# what the textarea was rendered with, posted back so an untouched textarea can be told
# from an edited one.
OVERRIDABLE_FIELDS = (
    "command_config",
    "reference_name",
    "chemistry",
    "probe_set",
    "command",
    "command_original",
)


def staff_required(view):
    """Allow staff users and return 403 for other users.

    Use this check instead of `user_passes_test`, which sends a failed test to LOGIN_URL. A signed-in user
        without staff would land on the sign-in form as though they had been logged out.
        `login_required` has already handled the anonymous case by the time this runs, so what
        is left is an authorisation failure.
    """

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("Uploading and activating configs is staff-only.")
        return view(request, *args, **kwargs)

    return wrapped


# --- dashboard and the submission flow -------------------------------------------------


@login_required
def dashboard(request):
    """List fastq samples and start a submission."""
    return render(request, "dashboard.html", _dashboard_context(request))


@login_required
def data_locations(request):
    """List S3 locations for the visible fastq samples and OCS stages."""
    queryset = _sorted(_filtered_samples(request), request)
    page_size = _page_size(request)
    page = Paginator(queryset, page_size).get_page(request.GET.get("page"))
    stage_filters = [
        {"stage": stage, "selected": request.GET.get(f"{stage.value}_status", "")}
        for stage in columns.LOCATION_STAGES
    ]
    selected_location_stage = request.GET.get("location_stage", "")
    location_rows = locations.stage_rows(page.object_list)
    if selected_location_stage in {stage.value for stage in columns.LOCATION_STAGES}:
        location_rows = [row for row in location_rows if row["stage"].value == selected_location_stage]
    prefix = request.GET.get("batch_prefix")
    scope = Sample.objects.all()
    if prefix in BatchPrefix.values:
        scope = scope.filter(batch_prefix=prefix)
    status_synced_at = (
        cache.get(sync.LAST_STATUS_SWEEP_KEY) or StageStatus.objects.aggregate(at=Max("synced_at"))["at"]
    )
    status_period = settings.CELERY_BEAT_SCHEDULE["sync-stage-statuses"]["schedule"]
    return render(
        request,
        "data_locations.html",
        {
            "page": page,
            "page_size": page_size,
            "page_size_options": PAGE_SIZE_OPTIONS,
            "location_rows": location_rows,
            "columns": columns.visible_location_columns(request.user),
            "all_columns": columns.LOCATION_COLUMNS,
            "column_groups": columns.LOCATION_COLUMN_GROUPS,
            "locked_column": "",
            "default_column_keys": columns.LOCATION_DEFAULT_COLUMNS,
            "visible_column_keys": [column.key for column in columns.visible_location_columns(request.user)],
            "batch_prefixes": _prefix_counts(),
            "selected_prefix": request.GET.get("batch_prefix", ""),
            "search": request.GET.get("fastq_name") or "",
            "studies": _study_options(),
            "selected_studies": request.GET.getlist("study"),
            "location_stages": columns.LOCATION_STAGES,
            "selected_location_stage": selected_location_stage,
            "filters": {field: request.GET.get(field, "") for field in FILTER_FIELDS},
            "stage_filters": stage_filters,
            "batches": _batch_options(request.GET.get("batch_name_from_vendor", ""), scope),
            "organisms": _scoped_distinct(scope, "organism_common_name"),
            "library_preps": _scoped_distinct(scope, "library_prep_method_name"),
            "statuses": [NOT_COMPLETED, *_scoped_statuses(scope)],
            "filters_open": any(request.GET.get(field) for field in FILTER_FIELDS)
            or any(row["selected"] for row in stage_filters),
            "active_filter_count": sum(1 for field in FILTER_FIELDS if request.GET.get(field))
            + sum(1 for row in stage_filters if row["selected"])
            + bool(request.GET.getlist("study")),
            "status_synced_at": status_synced_at,
            "status_refresh": _humanised_seconds(status_period),
            "status_stale": _is_stale(status_synced_at, status_period * 3),
        },
    )


@login_required
@require_POST
def export_data_locations_csv(request):
    """Return the selected or filtered Data Locations rows as CSV."""
    chosen = request.POST.getlist("fastq_names")
    samples = _sorted(_filtered_samples(request), request)
    if chosen:
        samples = samples.filter(fastq_name__in=chosen)

    rows = locations.stage_rows(samples)
    selected_location_stage = request.GET.get("location_stage", "")
    if selected_location_stage in {stage.value for stage in columns.LOCATION_STAGES}:
        rows = [row for row in rows if row["stage"].value == selected_location_stage]

    visible = columns.visible_location_columns(request.user)
    writer = csv.writer(_Echo())
    headers = ["Fastq Name", *(column.label for column in visible), "S3 Location"]

    def csv_text(value) -> str:
        text = "" if value is None else str(value)
        return f"'{text}" if text[:1] in ("=", "+", "-", "@") else text

    def csv_rows():
        yield writer.writerow(headers)
        for row in rows:
            values = []
            for column in visible:
                value = (
                    row["stage"].label
                    if column.key == "stage"
                    else row["status"]
                    if column.key == "status"
                    else row["column_values"].get(column.key, "")
                )
                if isinstance(value, list):
                    value = ", ".join(value)
                values.append(csv_text(value))
            yield writer.writerow([csv_text(row["fastq_name"]), *values, csv_text(row["s3_uri"])])

    response = StreamingHttpResponse(csv_rows(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="omicshub-data-locations.csv"'
    return response


@login_required
@require_GET
def data_location_contents(request, sample_id: int, stage: str):
    """List one folder from a stage's registered S3 file store."""
    if stage not in Stage.values:
        raise Http404("Unknown OCS stage")

    record = get_object_or_404(StageStatus, sample_id=sample_id, stage=stage)
    if not record.file_store_id:
        raise Http404("This stage has no file store")

    file_store = dynamodb.get_file_stores([record.file_store_id]).get(record.file_store_id)
    if not file_store or not file_store.get("s3_uri"):
        raise Http404("The file store record has no S3 location")

    prefix = request.GET.get("prefix", "").strip("/")
    token = request.GET.get("continuation_token") or None
    try:
        contents = s3.list_folder(str(file_store["s3_uri"]), prefix, token)
    except (BotoCoreError, ClientError) as error:
        logger.warning("S3 contents lookup failed for sample %s stage %s: %s", sample_id, stage, error)
        return render(
            request,
            "partials/data_location_contents.html",
            {
                "error": "Could not read this S3 location.",
                "s3_uri": file_store["s3_uri"],
            },
            status=502,
        )

    base_url = request.path
    parent_prefix = prefix.rpartition("/")[0]
    folder_links = [
        {
            "name": folder,
            "prefix": "/".join(part for part in (prefix, folder) if part),
            "url": f"{base_url}?{urlencode({'prefix': '/'.join(part for part in (prefix, folder) if part)})}",
        }
        for folder in contents.folders
    ]
    next_url = None
    if contents.next_token:
        next_url = f"{base_url}?{urlencode({'prefix': prefix, 'continuation_token': contents.next_token})}"

    return render(
        request,
        "partials/data_location_contents.html",
        {
            "s3_uri": file_store["s3_uri"],
            "prefix": prefix,
            "folders": folder_links,
            "files": contents.files,
            "next_url": next_url,
            "parent_url": (
                f"{base_url}?{urlencode({'prefix': parent_prefix})}" if parent_prefix else base_url
            )
            if prefix
            else None,
            "refresh_url": f"{base_url}?{urlencode({'prefix': prefix})}" if prefix else base_url,
            "download_url": reverse("web_ui:data-location-download", args=[sample_id, stage]),
        },
    )


@login_required
@require_POST
def download_data_location_files(request, sample_id: int, stage: str):
    """Stream selected S3 files and folders as one ZIP archive."""
    if stage not in Stage.values:
        raise Http404("Unknown OCS stage")

    record = get_object_or_404(StageStatus, sample_id=sample_id, stage=stage)
    sample = record.sample
    if not record.file_store_id:
        raise Http404("This stage has no file store")

    file_store = dynamodb.get_file_stores([record.file_store_id]).get(record.file_store_id)
    if not file_store or not file_store.get("s3_uri"):
        raise Http404("The file store record has no S3 location")

    keys = list(dict.fromkeys(request.POST.getlist("keys")))
    folders = list(dict.fromkeys(request.POST.getlist("folders")))
    if not keys and not folders:
        return JsonResponse({"error": "Select at least one file or folder."}, status=400)
    if len(keys) + len(folders) > DOWNLOAD_SELECTION_LIMIT:
        return JsonResponse(
            {"error": f"Select no more than {DOWNLOAD_SELECTION_LIMIT} files or folders."}, status=400
        )

    selected_keys: list[str] = []
    try:
        for key in keys:
            s3.validate_key(file_store["s3_uri"], key)
            selected_keys.append(key)
        for folder in folders:
            selected_keys.extend(s3.list_files(file_store["s3_uri"], folder))
        selected_keys = list(dict.fromkeys(selected_keys))
        if len(selected_keys) > DOWNLOAD_SELECTION_LIMIT:
            return JsonResponse(
                {"error": f"The selection contains more than {DOWNLOAD_SELECTION_LIMIT} files."},
                status=400,
            )
        if not selected_keys:
            return JsonResponse({"error": "The selected folders contain no files."}, status=400)
    except ValueError:
        return JsonResponse({"error": "One or more selected paths are outside this S3 location."}, status=400)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return JsonResponse({"error": "One or more selected paths are no longer available."}, status=400)
        logger.warning("S3 download authorization failed for sample %s stage %s", sample_id, stage)
        return JsonResponse({"error": "S3 could not read the selected paths."}, status=502)
    except BotoCoreError:
        logger.warning("S3 download authorization failed for sample %s stage %s", sample_id, stage)
        return JsonResponse({"error": "S3 could not read the selected paths."}, status=502)

    def stream_zip() -> Iterator[bytes]:
        output = _ZipOutput()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for key in selected_keys:
                body = s3.get_object_body(file_store["s3_uri"], key)
                try:
                    info = zipfile.ZipInfo(s3.relative_key(file_store["s3_uri"], key))
                    info.compress_type = zipfile.ZIP_STORED
                    with archive.open(info, "w") as target:
                        while chunk := body.read(1024 * 1024):
                            target.write(chunk)
                            yield from output.drain()
                finally:
                    body.close()
        yield from output.drain()

    filename = f"{_archive_part(sample.fastq_name)}-{_archive_part(stage)}.zip"
    response = StreamingHttpResponse(stream_zip(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class _ZipOutput(io.RawIOBase):
    """Collect ZIP writer chunks without buffering the archive."""

    def __init__(self) -> None:
        super().__init__()
        self.chunks: deque[bytes] = deque()
        self.position = 0

    def write(self, value: Buffer) -> int:
        chunk = bytes(value)
        self.chunks.append(chunk)
        self.position += len(chunk)
        return len(chunk)

    def tell(self) -> int:
        return self.position

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        return None

    def drain(self) -> Iterator[bytes]:
        while self.chunks:
            yield self.chunks.popleft()


def _archive_part(value: str) -> str:
    """Keep archive names readable while removing unsafe filename characters."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "download"


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
    """Refresh the visible fastq samples' stage status from OCS.

    The beat sweep already keeps the whole mirror within a few minutes of OCS, so this is
    not how status normally arrives. It exists for the moment someone does not believe the
    table: one page of samples is small enough to ask DynamoDB about directly, and what
    comes back is written to the same rows the sweep writes, so the answer is the table's
    answer rather than a second opinion rendered beside it.
    """
    # The page posts the rows it is showing, so this refreshes exactly what the reader is
    # looking at. Remove duplicate names before querying and reporting the count.
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
@require_GET
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
        # Fastq name identifies the row; hiding it would leave a table nobody can read.
        request.user.visible_columns = ["fastq_name", *[key for key in chosen if key != "fastq_name"]]
        request.user.save(update_fields=["visible_columns"])
    return redirect(_safe_next(request))


class _Echo:
    """Write a line and return it for a streaming CSV response."""

    def write(self, value):
        return value


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
        # A highlighted selection wins over the filters; without this an export would
        # quietly widen to every filtered row.
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


# --- cart ------------------------------------------------------------------------------


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
    # insert the same user can add the same sample again. A double-clicked button is enough,
    # and the unique constraint would turn the second request into a 500 rather than the
    # no-op it should be. The constraint stays; this is how the race lands on it quietly.
    CartItem.objects.bulk_create(
        [CartItem(user=request.user, sample=sample) for sample in samples if sample.pk not in in_cart],
        ignore_conflicts=True,
    )

    # Counted from what is actually stored, not from what was handed to bulk_create: with
    # ignore_conflicts the returned list includes rows that were silently dropped, so
    # trusting its length would report samples as added that were already there.
    added = len(_cart_sample_ids(request.user, samples)) - len(in_cart)
    return _cart_add_result(
        request,
        added=added,
        already=len(in_cart),
        # A page listing a sample the mirror no longer holds means someone else re-synced the
        # batch while this one sat open. Silently dropping it would leave a selection that
        # never arrived and no reason why.
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


# --- checkout and the submission flow ---------------------------------------------------


@login_required
def checkout(request):
    """Show the cart and the manifest used for its submissions."""
    return render(request, "checkout.html", _checkout_context(request))


@login_required
@require_POST
def submit_review(request):
    """Build the plan showing commands, skips, and missing manifest values."""
    context = _submission_context(request)
    if context is None:
        return redirect("web_ui:checkout")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "_submit_modal.html", context)
    return render(request, "checkout.html", {**context, "open_modal": "submit"})


@login_required
@require_POST
def command_preview(request):
    """Build one fastq sample command from the submitted editor values."""
    config = _selected_config(request)
    if config is None:
        return JsonResponse({"error": "No active workflow config."}, status=400)

    fastq_name = request.POST.get("fastq_name", "")
    sample = Sample.objects.filter(fastq_name=fastq_name).prefetch_related("stage_statuses").first()
    if sample is None:
        return JsonResponse({"error": f"No sample named {fastq_name!r}."}, status=404)

    # A multiome half is planned against its partner, so previewing one alone would report
    # `pair_missing` rather than the command it will actually get.
    samples, _ = pairing.with_multiome_partners([sample])

    form = SubmissionForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"error": str(next(iter(form.errors.values()))[0])}, status=400)

    plan = planning.build_plan(
        samples=samples,
        config=config.data,
        email=form.cleaned_data["email"] or request.user.email,
        modality=form.cleaned_data["modality"] or None,
        force=form.cleaned_data["force"] or None,
        batch_processing=form.cleaned_data["batch_processing"],
        command_config_choices=_command_config_choices(request),
        sample_overrides=_overrides_for(request, samples),
    )

    for entry in plan.entries:
        if entry.sample.fastq_name == fastq_name:
            return JsonResponse(
                {
                    "command": entry.command,
                    "command_config": entry.command_config_name,
                    "spacing": entry.spacing,
                    "edited": entry.edited,
                }
            )

    # No entry means this combination of choices produces nothing to run. Say which reason,
    # so the editor can show it rather than silently leaving the old command on screen.
    for skip in plan.skipped:
        if skip.sample.fastq_name == fastq_name:
            return JsonResponse({"error": skip.detail, "reason": skip.reason}, status=409)

    return JsonResponse({"error": "That sample is no longer part of this submission."}, status=409)


@login_required
@require_POST
def submit_commands(request):
    """Build the confirmation view with exact commands and the OCS notification address."""
    context = _submission_context(request)
    if context is None:
        return redirect("web_ui:checkout")
    return render(request, "checkout.html", {**context, "open_modal": "final"})


@login_required
@require_POST
def submit_confirm(request):
    """Queue the confirmed commands and remove queued samples from the cart."""
    context = _submission_context(request)
    if context is None:
        return redirect("web_ui:checkout")

    plan = context["plan"]
    if plan.needs_modality:
        messages.error(request, "Choose a modality for the samples that need one.")
        return redirect("web_ui:checkout")

    # Queueing and clearing the cart are one unit: a failure between them leaves the jobs
    # queued and still staged, and the user confirms the same submission again.
    with transaction.atomic():
        result = enqueue_service.enqueue(
            plan=plan,
            user=request.user,
            notify_email=context["submission"]["email"],
            forced=bool(context["submission"]["force"]),
            batch_processing=context["submission"]["batch_processing"],
        )
        # Only what reached the queue leaves the cart. A sample skipped because ingest is still
        # running stays staged so it can be submitted once it is ready,
        # which is the whole reason the cart outlives a single visit to this page.
        queued_names = {entry.sample.fastq_name for entry in result.created}
        queued_names |= {entry.sample.fastq_name for entry in result.already_queued}
        if queued_names:
            CartItem.objects.filter(user=request.user, sample__fastq_name__in=queued_names).delete()

    if result.created:
        messages.success(request, f"Queued {len(result.created)} jobs.")
    if result.already_queued:
        messages.info(request, f"{len(result.already_queued)} already queued; left alone.")
    if not result.created and not result.already_queued:
        messages.warning(request, "Nothing was queued. Every sample was skipped.")

    return redirect("web_ui:queue")


# --- queue -----------------------------------------------------------------------------


@login_required
def queue(request):
    entries = list(_owned(request).filter(status__in=QUEUED_STATUSES))
    next_entry = (
        None
        if request.user.queue_paused
        else next((e for e in entries if e.status == QueueEntry.Status.PENDING), None)
    )
    if cache.get(tasks.CAPACITY_HOLD_KEY):
        next_wait = "waiting for OCS capacity"
    elif seconds := tasks.hold_remaining_seconds(tasks.SPACING_HOLD_KEY):
        next_wait = f"in {_format_queue_wait(seconds)}"
    else:
        next_wait = "within 1 minute"
    return render(
        request,
        "queue.html",
        {
            "entries": entries,
            "next_entry": next_entry,
            "next_wait": next_wait,
            "queue_paused": request.user.queue_paused,
        },
    )


def _format_queue_wait(seconds: int) -> str:
    if seconds < 60:
        return f"{max(1, seconds)} seconds"
    return f"{(seconds + 59) // 60} minutes"


@login_required
@require_POST
def cancel(request, pk):
    entry = get_object_or_404(_owned(request), pk=pk)
    # Conditional on PENDING so the worker cannot claim it between the check and the write:
    # cancelling a job already on its way to OCS would leave the queue disagreeing with OCS.
    cancelled = QueueEntry.objects.filter(pk=entry.pk, status=QueueEntry.Status.PENDING).update(
        status=QueueEntry.Status.CANCELLED
    )
    if cancelled:
        messages.success(request, f"Cancelled {entry.sample.fastq_name}.")
    else:
        messages.error(request, f"{entry.sample.fastq_name} is already being submitted.")
    return redirect("web_ui:queue")


@login_required
@require_POST
def toggle_queue_pause(request):
    """Pause or resume this user's pending queue entries."""
    request.user.queue_paused = not request.user.queue_paused
    request.user.save(update_fields=["queue_paused"])
    state = "paused" if request.user.queue_paused else "resumed"
    messages.success(request, f"Your queue is {state}.")
    return redirect("web_ui:queue")


@login_required
@require_POST
def delete_queue_entry(request, pk):
    """Delete this user's pending queue entry without affecting OCS."""
    entry = get_object_or_404(_owned(request), pk=pk)
    deleted, _ = QueueEntry.objects.filter(pk=entry.pk, status=QueueEntry.Status.PENDING).delete()
    if deleted:
        messages.success(request, f"Deleted {entry.sample.fastq_name} from the queue.")
    else:
        messages.error(request, f"{entry.sample.fastq_name} is already being submitted.")
    return redirect("web_ui:queue")


# --- job monitor and failed jobs --------------------------------------------------------


@login_required
def job_monitor(request):
    """Show OCS stages that are running or finished."""
    submitted_here = QueueEntry.objects.filter(demand_id=OuterRef("demand_id")).exclude(demand_id="")
    running_stage = request.GET.get("running_stage")
    if running_stage not in {Stage.ALIGN, Stage.POST_ALIGN}:
        running_stage = ""

    stages = (
        StageStatus.objects.select_related("sample")
        .exclude(demand_id="")
        .annotate(queued_here=Exists(submitted_here))
    )

    running_stages = stages.filter(status__in=RUNNING_OCS_STATUSES)
    if running_stage:
        running_stages = running_stages.filter(stage=running_stage)
    running = list(running_stages.order_by(F("started_at").desc(nulls_last=True))[:MONITOR_ROWS])
    # Newest first and capped: the mirror holds every stage OCS has ever finished for
    # half a million samples, and this page answers "what happened lately".
    finished = list(
        stages.filter(status__in=FINISHED_OCS_STATUSES).order_by(F("last_update_time").desc(nulls_last=True))[
            :MONITOR_ROWS
        ]
    )
    monitor_running, monitor_finished = _collapse_multiome_monitor_rows(running, finished)
    monitor_fastq_names = list(dict.fromkeys(row.sample.fastq_name for row in [*running, *finished]))
    running_page_size = _page_size(request, "running_page_size")
    finished_page_size = _page_size(request, "finished_page_size")
    running_page = Paginator(monitor_running, running_page_size).get_page(request.GET.get("running_page"))
    finished_page = Paginator(monitor_finished, finished_page_size).get_page(request.GET.get("finished_page"))

    context = {
        "running": running_page,
        "finished": finished_page,
        "running_page": running_page,
        "finished_page": finished_page,
        "running_page_size": running_page_size,
        "finished_page_size": finished_page_size,
        "page_size_options": PAGE_SIZE_OPTIONS,
        "monitor_fastq_names": monitor_fastq_names,
        "row_limit": MONITOR_ROWS,
        "running_stage": running_stage,
        "running_stage_options": _monitor_stage_options(request),
        "counts": {
            "align": sum(1 for row in monitor_running if row.stage == Stage.ALIGN),
            "post_align": sum(1 for row in monitor_running if row.stage == Stage.POST_ALIGN),
            "total": len(monitor_running),
        },
        # The queue is this app's own, so these two stay scoped to the reader.
        **_owned(request).aggregate(
            queued=Count("pk", filter=Q(status__in=QUEUED_STATUSES)),
            failed=Count("pk", filter=Q(status__in=FAILED_STATUSES)),
        ),
    }
    template = (
        "partials/job_monitor_tables.html"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest"
        else "job_monitor.html"
    )
    return render(request, template, context)


def _monitor_stage_options(request):
    """Build the Running table's stage filter links."""
    options = [("", "All"), (Stage.ALIGN, "Alignment"), (Stage.POST_ALIGN, "Post-alignment")]
    result = []
    for value, label in options:
        query = request.GET.copy()
        query.pop("running_page", None)
        if value:
            query["running_stage"] = value
        else:
            query.pop("running_stage", None)
        result.append({"label": label, "value": value, "url": f"?{query.urlencode()}"})
    return result


def _collapse_multiome_monitor_rows(
    running: Sequence[StageStatus], finished: Sequence[StageStatus]
) -> tuple[list[StageStatus], list[StageStatus]]:
    """Represent a multiome MTX/ATX pair as one MTX monitor row.

    OCS mirrors a status for each FASTQ half, but the two halves share one alignment
    operation. A running half takes precedence over a finished half, and the MTX/GEX half
    is the representative whenever both statuses are in the same state.
    """
    selected: dict[tuple[str, str | int], StageStatus] = {}
    order: list[tuple[str, str | int]] = []

    for row in [*running, *finished]:
        sample = row.sample
        is_multiome = sample.library_prep_method_name in MULTIOME_PREPS and sample.load_name
        key = (row.stage, sample.load_name) if is_multiome else ("sample", row.pk)
        current = selected.get(key)
        if current is None:
            selected[key] = row
            order.append(key)
            continue

        current_is_running = current.status in RUNNING_OCS_STATUSES
        row_is_running = row.status in RUNNING_OCS_STATUSES
        current_is_mtx = current.sample.batch_prefix == BatchPrefix.MTX
        row_is_mtx = sample.batch_prefix == BatchPrefix.MTX
        if (row_is_running and not current_is_running) or (
            row_is_running == current_is_running and row_is_mtx and not current_is_mtx
        ):
            selected[key] = row

    collapsed = [selected[key] for key in order]
    return (
        [row for row in collapsed if row.status in RUNNING_OCS_STATUSES],
        [row for row in collapsed if row.status in FINISHED_OCS_STATUSES],
    )


@login_required
def failed_jobs(request):
    owned = _owned(request).select_related("sample", "requested_by")
    entries = owned.filter(status__in=FAILED_STATUSES, demand_id="")
    running_failures = owned.filter(status=QueueEntry.Status.FAILED).exclude(demand_id="")
    entries = list(entries)
    running_failures = list(running_failures)
    for entry in [*entries, *running_failures]:
        entry.can_retry = True
    return render(
        request,
        "failed_jobs.html",
        {
            "entries": entries,
            "running_failures": running_failures,
            "failure_count": len(entries) + len(running_failures),
        },
    )


@login_required
@require_POST
def retry_job(request, pk):
    """Return a retryable failed job to the pending queue."""
    entry = get_object_or_404(_owned(request), pk=pk)
    # Conditional on FAILED for the same reason `cancel` is conditional on PENDING: the
    # worker may claim the entry between reading it and writing it back.
    if QueueEntry.objects.filter(
        pk=entry.pk,
        status=QueueEntry.Status.FAILED,
    ).update(
        status=QueueEntry.Status.PENDING,
        demand_id="",
        submitted_at=None,
        error_message="",
    ):
        messages.success(request, f"{entry.sample.fastq_name} is back on the queue.")
    else:
        messages.error(request, f"{entry.sample.fastq_name} is {entry.status} and cannot be retried.")
    return redirect("web_ui:failed")


@login_required
@require_POST
def delete_job(request, pk):
    entry = get_object_or_404(_owned(request), pk=pk)
    if entry.status not in FAILED_STATUSES:
        messages.error(request, "Only failed entries can be deleted.")
    else:
        fastq_name = entry.sample.fastq_name
        entry.delete()
        messages.success(request, f"Deleted the failed entry for {fastq_name}.")
    return redirect("web_ui:failed")


# --- settings --------------------------------------------------------------------------


@login_required
@staff_required
def configs(request):
    """Show settings for uploading and activating the submission manifest."""
    if request.method == "POST":
        form = ConfigUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            for error in form.errors.values():
                messages.error(request, str(error[0]))
            return redirect("web_ui:configs")

        name = form.cleaned_data["file"].name
        try:
            manifest_service.create_config(raw=form.raw, name=name[:255], user=request.user)
        except ValidationError as error:
            messages.error(request, f"{name} was rejected: {'; '.join(error.messages)}")
            return redirect("web_ui:configs")

        messages.success(request, f"Uploaded {name}. Activate it to start using it.")
        return redirect("web_ui:configs")

    return render(
        request,
        "workflow_manifests.html",
        {"configs": WorkflowConfig.objects.select_related("uploaded_by")},
    )


@login_required
@staff_required
@require_POST
def activate_config(request, pk):
    config = get_object_or_404(WorkflowConfig, pk=pk)
    config.activate()
    messages.success(request, f"{config.name} is now active.")
    return redirect("web_ui:configs")


# --- helpers ---------------------------------------------------------------------------


def _filtered_samples(request):
    """Return samples matching the dashboard filters."""
    queryset = Sample.objects.prefetch_related("stage_statuses")

    for field in FILTER_FIELDS:
        value = request.GET.get(field)
        if value:
            queryset = queryset.filter(**{field: value})

    search = request.GET.get("fastq_name")
    if search:
        queryset = queryset.filter(
            Q(fastq_name__icontains=search)
            | Q(load_name__icontains=search)
            | Q(batch_name_from_vendor__icontains=search)
        )

    # The family toggle. Filters on the stored prefix, not the modality, so ATX stays
    # selectable on its own even though it runs as MTX.
    prefix = request.GET.get("batch_prefix")
    if prefix in BatchPrefix.values:
        queryset = queryset.filter(batch_prefix=prefix)

    studies = request.GET.getlist("study")
    if studies:
        study_filter = Q(studies__contains=[studies[0]])
        for study in studies[1:]:
            study_filter |= Q(studies__contains=[study])
        queryset = queryset.filter(study_filter)

    for stage in Stage:
        value = request.GET.get(f"{stage.value}_status")
        if not value:
            continue
        if value == NOT_COMPLETED:
            # No row for that stage at all is what "not completed" means.
            queryset = queryset.exclude(stage_statuses__stage=stage.value)
        else:
            queryset = queryset.filter(stage_statuses__stage=stage.value, stage_statuses__status=value)

    return queryset


def _dashboard_context(request):
    queryset = _sorted(_filtered_samples(request), request)
    stage_filters = [
        {"stage": stage, "selected": request.GET.get(f"{stage.value}_status", "")} for stage in Stage
    ]

    metadata_synced_at = Sample.objects.aggregate(at=Max("synced_at"))["at"]
    # When the sweep last *looked*, not when a row last changed: the sweep only writes rows
    # OCS actually moved, so Max(synced_at) stops advancing over a quiet pipeline and would
    # report healthy data as hours stale. The rows' own timestamps are the fallback for a
    # flushed cache, and read older than the truth rather than newer.
    status_synced_at = (
        cache.get(sync.LAST_STATUS_SWEEP_KEY) or StageStatus.objects.aggregate(at=Max("synced_at"))["at"]
    )
    status_period = settings.CELERY_BEAT_SCHEDULE["sync-stage-statuses"]["schedule"]

    # The tab, and only the tab. The advanced-filter menus are built from this rather than
    # the whole mirror so they offer values that can actually return rows, and rather than
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
        "filters": {field: request.GET.get(field, "") for field in FILTER_FIELDS},
        "stage_filters": stage_filters,
        # Which column the table is ordered by, so the header can show the arrow.
        "sort": request.GET.get("sort") if request.GET.get("sort") in SORTABLE else DEFAULT_SORT,
        "dir": "asc" if request.GET.get("dir") == "asc" else "desc",
        "sortable_keys": list(SORTABLE),
        # How often the two sweeps run, for the freshness clock tooltip. Otherwise
        # "3 minutes old" gives no way to tell stale from simply not-due-yet.
        "metadata_refresh": "nightly at 03:00",
        "status_refresh": _humanised_seconds(status_period),
        "batch_prefixes": _prefix_counts(),
        "selected_prefix": request.GET.get("batch_prefix", ""),
        "studies": _study_options(),
        "selected_studies": request.GET.getlist("study"),
        "modalities": modality.available_modalities(config.data) if config else [],
        # Filter options come from what is actually in the mirror, so a dropdown never
        # offers a value that would return nothing. That is what keeps the batch menu
        # short: OCS has nearly two thousand batches, the mirror only the synced ones.
        # Scoped to the selected tab. On the MTX tab the batch menu lists MTX batches and
        # nothing else. Offering RTX batches there produces a filter combination that can
        # only ever return an empty table.
        "batches": _batch_options(request.GET.get("batch_name_from_vendor", ""), scope),
        "organisms": _scoped_distinct(scope, "organism_common_name"),
        "library_preps": _scoped_distinct(scope, "library_prep_method_name"),
        "statuses": [NOT_COMPLETED, *_scoped_statuses(scope)],
        "filters_open": any(request.GET.get(field) for field in FILTER_FIELDS)
        or any(row["selected"] for row in stage_filters),
        # How many advanced filters are narrowing the table. The panel that holds them is
        # collapsed by default, so without a count on its own button the only way to learn
        # that four of them are active is to open it and read six menus. Status belongs
        # where the control is, not one disclosure away from it.
        "active_filter_count": sum(1 for field in FILTER_FIELDS if request.GET.get(field))
        + sum(1 for row in stage_filters if row["selected"]),
        # Shown in the header so nobody has to guess how current the table is.
        "metadata_synced_at": metadata_synced_at,
        "status_synced_at": status_synced_at,
        # A clock that only says "4 hours old" leaves the reader to work out whether that is
        # normal. This says whether it is: stale means the sweep has missed several turns,
        # which in practice means the beat scheduler or the worker is not running. The
        # thing a staleness indicator should actually be able to tell you.
        "status_stale": _is_stale(status_synced_at, status_period * 3),
    }


def batch_sort_key(name: str) -> tuple[int, str]:
    """Sort vendor batch names by their numeric suffix.

    Alphabetically "MTX-9" lands after "MTX-10" and "MTX-12001" before "MTX-2001", so a
    text sort puts neither the newest nor the highest batch where a reader expects it. The
    digits are compared as an integer, with the raw name breaking ties between names that
    share a number. A name with no digits sorts last.
    """
    digits = "".join(character for character in name if character.isdigit())
    return (int(digits) if digits else -1, name)


def _batch_options(selected: str, scope) -> list[str]:
    """Return vendor batches for the filter menu, newest first."""
    batches = _scoped_distinct(scope, "batch_name_from_vendor")
    if selected and selected not in batches:
        batches.append(selected)
    return sorted(batches, key=batch_sort_key, reverse=True)


def _page_size(request, parameter: str = "page_size") -> int:
    """Return the selected table page size."""
    try:
        page_size = int(request.GET.get(parameter, PAGE_SIZE))
    except (TypeError, ValueError):
        return PAGE_SIZE
    return page_size if page_size in PAGE_SIZE_OPTIONS else PAGE_SIZE


# Columns the table can be sorted by, mapped to what that means in SQL. An allowlist
# rather than trusting the parameter: order_by takes a field path, and an arbitrary one
# lets a caller sort by (and so probe) any related column.
SORTABLE = {
    "fastq_name": ("fastq_name",),
    "batch_name_from_vendor": ("batch_number", "batch_name_from_vendor"),
    "batch_name": ("batch_name",),
    "load_name": ("load_name",),
    "modality": ("modality",),
    "organism_common_name": ("organism_common_name",),
    "library_prep_method_name": ("library_prep_method_name",),
    "studies": ("studies",),
    "sample_type": ("sample_type",),
    "amplification_name": ("amplification_name",),
    "sequencing_vendor": ("sequencing_vendor",),
    "alignment_method": ("alignment_method",),
}
DEFAULT_SORT = "batch_name_from_vendor"
DEFAULT_DIRECTION = "desc"


def _sorted(queryset, request):
    """Return table rows ordered by the selected sort, newest batch first by default.

    Batch names sort by the number inside them. Use `batch_sort_key`, which applies the same
        rule applied to the filter menu in Python.
    """
    field = request.GET.get("sort") or DEFAULT_SORT
    if field not in SORTABLE:
        field = DEFAULT_SORT
    direction = request.GET.get("dir") or DEFAULT_DIRECTION
    descending = direction != "asc"

    queryset = queryset.annotate(
        batch_number=Cast(
            NullIf(
                Func(
                    F("batch_name_from_vendor"),
                    Value(r"\D"),
                    Value(""),
                    Value("g"),
                    function="regexp_replace",
                ),
                Value(""),
            ),
            output_field=BigIntegerField(),
        )
    )

    # nulls_last on every part, because Postgres sorts NULL first under DESC and a batch
    # name with no digits in it has a NULL `batch_number`. Left to the default, `MTX-PILOT`
    # sat at the top of the table and the bottom of the filter menu, which sorts the same
    # names in Python. See `batch_sort_key`.
    ordering = [
        F(part).desc(nulls_last=True) if descending else F(part).asc(nulls_last=True)
        for part in SORTABLE[field]
    ]
    # A unique tiebreaker, or rows shift between pages when the sort key repeats.
    ordering.append(F("fastq_name").desc() if descending else F("fastq_name").asc())
    return queryset.order_by(*ordering)


def _is_stale(synced_at, tolerance_seconds) -> bool:
    """Return whether a stage-status sweep is late enough to flag as stale.

    Never synced counts as stale: an empty mirror and a dead scheduler look identical from
    the dashboard, and both want the same response from the reader.
    """
    if synced_at is None:
        return True
    return (timezone.now() - synced_at).total_seconds() > tolerance_seconds


def _humanised_seconds(schedule) -> str:
    """Return the sweep interval text shown beside the staleness clock."""
    minutes = int(schedule) // 60
    if minutes >= 60:
        hours = minutes // 60
        return f"every {hours} hour{'s' if hours != 1 else ''}"
    if minutes:
        return f"every {minutes} minute{'s' if minutes != 1 else ''}"
    return f"every {int(schedule)} seconds"


def _scoped_distinct(scope, field) -> list[str]:
    """Return distinct values of `field` in the current tab."""
    return list(scope.order_by(field).values_list(field, flat=True).distinct())


def _scoped_statuses(scope) -> list[str]:
    """Return OCS status labels present in the current tab."""
    return list(
        StageStatus.objects.filter(sample__in=scope)
        .order_by("status")
        .values_list("status", flat=True)
        .distinct()
    )


def _prefix_counts() -> list[dict]:
    """Return each vendor family with its fastq sample count in display order.

    Counted over the whole mirror rather than the current filter, so the numbers do not
    move as you click between families.
    """
    counts = dict(
        Sample.objects.values("batch_prefix").annotate(n=Count("id")).values_list("batch_prefix", "n")
    )
    return [
        {"value": prefix.value, "label": prefix.label, "count": counts.get(prefix.value, 0)}
        for prefix in TAB_ORDER
    ]


def _study_options() -> list[str]:
    """Return distinct study names for the filter menu.

    `studies` is a JSON array, so the values are unnested in Postgres rather than read
    into Python: the answer is tens of names, but reading it row by row meant pulling the
    column off every sample in the mirror on every dashboard render. Cached because it
    only changes when a sync runs.
    """
    studies = cache.get(sync.STUDY_OPTIONS_KEY)
    if studies is None:
        studies = sorted(
            Sample.objects.annotate(study=Func(F("studies"), function="jsonb_array_elements_text"))
            .values_list("study", flat=True)
            # Meta.ordering would otherwise be appended to the SELECT DISTINCT, making the
            # distinct run over (study, fastq_name) and repeating each study once per sample.
            .order_by()
            .distinct()
        )
        cache.set(sync.STUDY_OPTIONS_KEY, studies, timeout=600)
    return studies


def _cart_items(request):
    return (
        CartItem.objects.filter(user=request.user)
        .select_related("sample")
        .prefetch_related("sample__stage_statuses")
    )


def _selected_config(request):
    """Return the manifest used to build this submission.

    A manifest may be named explicitly. The checkout page's picker posts `config_id` and
    carries it through every step, so a user can check a submission against a manifest
        before it is the active one. Absent that, the active config is used, which is what the
        API and the worker also read.
    """
    config_id = request.POST.get("config_id") or request.GET.get("config_id")
    if config_id and config_id.isdigit():
        config = WorkflowConfig.objects.filter(pk=config_id).first()
        if config is not None:
            return config
    return WorkflowConfig.objects.filter(is_active=True).first()


def _checkout_context(request):
    """Build the cart page with staged samples and the selected manifest."""
    items = list(_cart_items(request))
    config = _selected_config(request)

    return {
        "cart_items": items,
        # Fixed, not the user's dashboard choice. See columns.CHECKOUT_COLUMNS.
        "columns": columns.CHECKOUT_COLUMN_LIST,
        "config": config,
        "configs": list(WorkflowConfig.objects.select_related("uploaded_by")),
        "modalities": modality.available_modalities(config.data) if config else [],
    }


def _submission_context(request):
    """Plan the posted fastq sample selection and gather modal data.

    Return None after messaging the user when there is nothing to plan.
    """
    config = _selected_config(request)
    if config is None:
        messages.error(request, "No active workflow config. Upload and activate one first.")
        return None

    fastq_names = request.POST.getlist("fastq_names")
    samples = list(Sample.objects.filter(fastq_name__in=fastq_names).prefetch_related("stage_statuses"))
    if not samples:
        messages.error(request, "Select at least one sample to submit.")
        return None

    # A multiome pair has to go together: the GEX and ATAC halves are aligned as one, so
    # submitting half of one is a run that cannot finish. Said out loud rather than done
    # quietly, because the user is about to see more samples than they ticked.
    samples, added_partners = pairing.with_multiome_partners(samples)
    if added_partners:
        names = ", ".join(sample.fastq_name for sample in added_partners)
        messages.info(request, f"Added {len(added_partners)} multiome partner(s) to the selection: {names}.")

    form = SubmissionForm(request.POST)
    if not form.is_valid():
        for error in form.errors.values():
            messages.error(request, str(error[0]))
        return None

    submission = {
        "fastq_names": [sample.fastq_name for sample in samples],
        "modality": form.cleaned_data["modality"],
        "force": form.cleaned_data["force"],
        "batch_processing": form.cleaned_data["batch_processing"],
        "email": form.cleaned_data["email"] or request.user.email,
        "choices": _command_config_choices(request),
        "overrides": _overrides_for(request, samples),
        "config_id": str(config.pk),
    }

    plan = planning.build_plan(
        samples=samples,
        config=config.data,
        email=submission["email"],
        modality=submission["modality"] or None,
        force=submission["force"] or None,
        batch_processing=submission["batch_processing"],
        command_config_choices=submission["choices"],
        sample_overrides=submission["overrides"],
    )

    # needs_command_config recomputes on every access, so the groups are enriched once here
    # and passed on rather than mutated in place.
    unconfigured_groups = plan.needs_command_config
    for group in unconfigured_groups:
        group["options"] = command_builder.available_command_configs(
            config.data, group["modality"], group["stage"]
        )

    return {
        **_checkout_context(request),
        "plan": plan,
        "unconfigured_groups": unconfigured_groups,
        # Placeholders the config cannot fill for this prep. Asked for in the modal, and
        # carried forward as hidden fields so the confirm step re-plans with the same
        # answers rather than rediscovering the gap.
        "value_groups": plan.needs_values,
        # Whether closing the modal would throw away decisions the user made in it. Only
        # these three survive nothing but a re-plan: a workflow they picked, an asset they
        # chose for an unlisted prep, and any per-sample edit. Without something to lose,
        # closing costs nothing and asking about it is the kind of prompt people learn to
        # dismiss without reading, which makes the prompt useless when it matters.
        "has_unsaved_choices": bool(
            submission["overrides"] or submission["choices"] or submission["modality"]
        ),
        "submission": submission,
        # Posted back as "stage::library prep::config name" so one field carries all three.
        "choice_values": [
            f"{stage}::{prep}::{name}" for (stage, prep), name in submission["choices"].items()
        ],
        "align_groups": _batch_groups(plan, Stage.ALIGN, config.data),
        "postalign_groups": _batch_groups(plan, Stage.POST_ALIGN, config.data),
        "align_entries": [e for e in plan.entries if e.stage == Stage.ALIGN],
        "postalign_entries": [e for e in plan.entries if e.stage == Stage.POST_ALIGN],
    }


def _batch_groups(plan, stage: str, config: dict) -> list[dict]:
    """Return planned entries for one stage grouped by vendor batch.

    Each entry carries what its editor needs, including alternative command configs for its
    modality and stage and the reference and chemistry values the manifest offers for its
    organism. The template therefore renders the form without reaching back into the manifest.
    """
    groups: dict[str, dict] = {}
    for entry in plan.entries:
        if entry.stage != stage:
            continue
        batch = entry.sample.batch_name_from_vendor or "not provided"
        group = groups.setdefault(batch, {"batch": batch, "entries": []})
        group["entries"].append(
            {
                "entry": entry,
                "options": command_builder.available_command_configs(config, entry.modality, stage),
                # Passing the command config narrows the editor to the fields this command
                # actually substitutes. There is no Reference menu above a post-QC command, which
                # names no genome and could not have used the value.
                "fields": command_builder.placeholder_fields(
                    config,
                    entry.modality,
                    entry.sample.organism_common_name,
                    command_config=_command_config_for(config, entry, stage),
                ),
            }
        )
    return list(groups.values())


def _command_config_for(config: dict, entry, stage: str) -> dict | None:
    """Return the command config for a planned entry, or None when it is missing.

    A hand-edited entry can name a config that no longer resolves; the editor falls back to
    offering every field rather than failing to render the row.
    """
    try:
        return command_builder.command_config_by_name(
            config=config, modality=entry.modality, stage=stage, name=entry.command_config_name
        )
    except command_builder.ConfigurationError:
        return None


def _sample_overrides(request) -> dict[str, dict]:
    """Return submit-modal edits keyed by fastq name.

    Post one field per `(sample, attribute)`, such as `override__<fastq>__reference_name`,
    rather than a single blob, so a browser submitting the form without JavaScript
        still carries exactly what the user changed.

        The command textarea always posts, and a hand-edited command outranks the menus, so an
        untouched one would outrank a reference the user had just chosen. The editor posts the
        command it rendered alongside it; if what came back is that same string the textarea
        was not touched, and it is dropped so the menus decide.
    """
    overrides: dict[str, dict] = {}
    originals: dict[str, str] = {}

    for key, value in request.POST.items():
        if not key.startswith("override__"):
            continue
        fastq_name, separator, field = key.removeprefix("override__").partition("__")
        if not separator:
            continue
        if field == "command_original":
            originals[fastq_name] = value
            continue
        if field not in OVERRIDABLE_FIELDS:
            continue
        if value:
            overrides.setdefault(fastq_name, {})[field] = value

    for fastq_name, fields in overrides.items():
        original = originals.get(fastq_name)
        if original is not None and fields.get("command", "").strip() == original.strip():
            fields.pop("command", None)

    return overrides


def _overrides_for(request, samples) -> dict[str, dict]:
    """Return all submission edits keyed by fastq name.

    Two sources, merged in precedence order: the per-prep answers to a missing placeholder,
    then the per-row edits from the command editor. A row the user edited by hand wins over
    the group answer that reached it, which is the order they made the two choices in.
    """
    merged: dict[str, dict] = {}
    for fastq_name, fields in _missing_value_answers(request, samples).items():
        merged.setdefault(fastq_name, {}).update(fields)
    for fastq_name, fields in _sample_overrides(request).items():
        merged.setdefault(fastq_name, {}).update(fields)
    return merged


def _missing_value_answers(request, samples) -> dict[str, dict]:
    """Return values supplied for placeholders the manifest could not fill.

        Posted as `missing__<stage>__<library prep>__<field>`, because the cause is the library
    prep rather than any one sample, so one answer covers every sample sharing that prep,
        and it is expanded here into the same per-sample override dict everything else uses.

        The value only reaches a sample whose prep it was given for, so an answer cannot leak
        onto an unrelated sample if the selection changes between steps.
    """
    answers: dict[str, dict] = {}
    for key, value in request.POST.items():
        if not key.startswith("missing__") or not value.strip():
            continue
        try:
            _, stage, prep, field = key.split("__", 3)
        except ValueError:
            continue
        if field not in OVERRIDABLE_FIELDS:
            continue
        for sample in samples:
            if sample.library_prep_method_name == prep:
                answers.setdefault(sample.fastq_name, {})[field] = value.strip()
    return answers


def _command_config_choices(request) -> dict[tuple[str, str], str]:
    """Return the command config selected for each unlisted library prep.

    Posted as "stage::library prep::name", so one menu carries all three. Anything that
    does not parse into three parts is ignored rather than raising: the planner then
    reports the prep as unconfigured, which is the state the user is being asked about.
    """
    choices = {}
    for value in request.POST.getlist("command_config_choice"):
        stage, _, remainder = value.partition("::")
        prep, _, name = remainder.partition("::")
        if name:
            choices[(stage, prep)] = name
    return choices


def _safe_next(request, fallback="web_ui:dashboard"):
    """Return the safe redirect target after a POST.

    `next` is attacker-controllable and resolve_url returns an unrecognised string
    unchanged, so an absolute URL would redirect straight off-site. This is the same guard
    django.contrib.auth.views.LoginView applies to its own next parameter.
    """
    target = request.POST.get("next")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback


def _owned(request):
    queryset = QueueEntry.objects.select_related("sample", "requested_by")
    return queryset if request.user.is_staff else queryset.filter(requested_by=request.user)
