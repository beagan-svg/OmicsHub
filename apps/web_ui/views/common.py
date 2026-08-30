"""Shared view helpers and settings used by the web UI views."""

import logging
from collections.abc import Sequence
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models import BigIntegerField, Count, F, Func, Max, Q, Value
from django.db.models.functions import Cast, NullIf
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.sample_catalog import ocs_sync as sync
from apps.sample_catalog.models import NOT_COMPLETED, BatchPrefix, Sample, Stage, StageStatus
from apps.submission_queue.models import QueueEntry

logger = logging.getLogger(__name__)

FILTER_FIELDS = ("batch_name_from_vendor", "organism_common_name", "library_prep_method_name")
PAGE_SIZE = 50
PAGE_SIZE_OPTIONS = (25, 50, 100, 200)
DOWNLOAD_SELECTION_LIMIT = 1000


class _Echo:
    """Return CSV text directly to a streaming response."""

    def write(self, value):
        return value


# The family tabs read in this order, which is not the order the model declares them in:
# declaration order answers to the data, this is a reading order.
TAB_ORDER = (BatchPrefix.RTX, BatchPrefix.RFX, BatchPrefix.MTX, BatchPrefix.ATX)

QUEUED_STATUSES = [QueueEntry.Status.PENDING, QueueEntry.Status.SUBMITTING]
FAILED_STATUSES = [QueueEntry.Status.FAILED]

# OCS's own labels, as they arrive from DynamoDB. The monitor reads these rather than queue
# statuses so it covers demands this app never submitted. AWAITING_TRIGGER and PENDING are
# running rather than finished: OCS has the job and has not started it, which is still work
# in flight from anyone watching the pipeline.
RUNNING_OCS_STATUSES = ("IN_PROGRESS", "SUBMITTED", "SUBMITTING", "PENDING", "AWAITING_TRIGGER")
FINISHED_OCS_STATUSES = ("COMPLETED", "ARCHIVED", "FAILED", "ABORTED", "STRANDED")

# The local database holds every stage OCS has run for half a million samples. The monitor shows
# the most recent, and says so on the page rather than implying it is the whole picture.
MONITOR_ROWS = 1000
TIMELINE_DAYS = 7
TIMELINE_PAGE_SIZE = 25

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

SORTABLE = {
    "fastq_name": ("fastq_number", "fastq_name"),
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
NUMERIC_SORT_SOURCE_FIELDS = {
    "batch_number": "batch_name_from_vendor",
    "fastq_number": "fastq_name",
}


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


def _filtered_samples(request):
    """Return samples matching the dashboard filters."""
    queryset = Sample.objects.prefetch_related("stage_statuses")

    for field in FILTER_FIELDS:
        values = request.GET.getlist(field)
        if values:
            queryset = queryset.filter(**{f"{field}__in": values})

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


def _status_sync_context():
    """Return the shared stage-status freshness values for dashboard headers."""
    status_synced_at = (
        cache.get(sync.LAST_STATUS_SWEEP_KEY) or StageStatus.objects.aggregate(at=Max("synced_at"))["at"]
    )
    status_period = settings.CELERY_BEAT_SCHEDULE["sync-stage-statuses"]["schedule"]
    return {
        "status_synced_at": status_synced_at,
        "status_refresh": _humanised_seconds(status_period),
        "status_stale": _is_stale(status_synced_at, status_period * 3),
    }


def _page_size(request, parameter: str = "page_size") -> int:
    """Return the selected table page size."""
    try:
        page_size = int(request.GET.get(parameter, PAGE_SIZE))
    except (TypeError, ValueError):
        return PAGE_SIZE
    return page_size if page_size in PAGE_SIZE_OPTIONS else PAGE_SIZE


def _numeric_sort_annotation(source_field: str) -> Cast:
    """Return the digits of `source_field` as one integer, or NULL if it has none."""
    return Cast(
        NullIf(
            Func(F(source_field), Value(r"\D"), Value(""), Value("g"), function="regexp_replace"),
            Value(""),
        ),
        output_field=BigIntegerField(),
    )


def _sorted(queryset, request):
    """Return table rows ordered by the selected sort, newest batch first by default.

    Batch names and fastq names both sort by the number inside them, not the text. See
    `batch_sort_key`, which applies the same rule to the batch filter menu in Python.
    """
    field = request.GET.get("sort") or DEFAULT_SORT
    if field not in SORTABLE:
        field = DEFAULT_SORT
    direction = request.GET.get("dir") or DEFAULT_DIRECTION
    descending = direction != "asc"

    parts = SORTABLE[field]
    numeric_annotations = {
        name: _numeric_sort_annotation(source)
        for name, source in NUMERIC_SORT_SOURCE_FIELDS.items()
        if name in parts
    }
    if numeric_annotations:
        queryset = queryset.annotate(**numeric_annotations)

    # nulls_last on every part, because Postgres sorts NULL first under DESC and a batch
    # name with no digits in it has a NULL `batch_number`. Left to the default, `MTX-PILOT`
    # sat at the top of the table and the bottom of the filter menu, which sorts the same
    # names in Python. See `batch_sort_key`.
    ordering = [
        F(part).desc(nulls_last=True) if descending else F(part).asc(nulls_last=True) for part in parts
    ]
    # A unique tiebreaker, or rows shift between pages when the sort key repeats.
    ordering.append(F("fastq_name").desc() if descending else F("fastq_name").asc())
    return queryset.order_by(*ordering)


def _is_stale(synced_at, tolerance_seconds) -> bool:
    """Return whether a stage-status sweep is late enough to flag as stale.

    Never synced counts as stale: an empty local database and a dead scheduler look identical from
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


def batch_sort_key(name: str) -> tuple[int, str]:
    """Sort batch names from the vendor by numeric suffix, then by name."""
    digits = "".join(character for character in name if character.isdigit())
    return (int(digits) if digits else -1, name)


def _batch_options(selected: Sequence[str], scope) -> list[str]:
    """Return batch names from the vendor for the current filter scope."""
    batches = _scoped_distinct(scope, "batch_name_from_vendor")
    for value in selected:
        if value not in batches:
            batches.append(value)
    return sorted(batches, key=batch_sort_key, reverse=True)


def export_csv_filename(*, data_locations: bool = False) -> str:
    """Build a timestamped filename for a CSV export."""
    timestamp = timezone.localtime(timezone.now()).strftime("%m-%d-%Y_%H%M")
    suffix = "export_s3" if data_locations else "export"
    return f"{timestamp}_{suffix}.csv"


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

    Counted over the whole local database rather than the current filter, so the numbers do not
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
    column off every sample in the local database on every dashboard render. Cached because it
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


def _safe_next(request, fallback="web_ui:dashboard"):
    """Return the validated local redirect target after a POST."""
    target = request.POST.get("next")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback


def _owned(request):
    queryset = QueueEntry.objects.select_related("sample", "requested_by")
    return queryset if request.user.is_staff else queryset.filter(requested_by=request.user)
