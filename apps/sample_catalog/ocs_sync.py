"""Load OCS metadata and stage status into the local mirror."""

from __future__ import annotations

import datetime as dt
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

from django.core.cache import cache
from django.db.models import Q

from apps.ocs_integration import dynamodb
from apps.sample_catalog.models import Sample, Stage, StageStatus, prefixes_for_workflows

logger = logging.getLogger(__name__)

# fastq-history is partitioned by fastq name, so a batch costs one query per sample.
# Syncing a few hundred samples serially takes tens of seconds; these are independent
# network calls, so they are made concurrently.
HISTORY_FETCH_WORKERS = 8

# Rows per INSERT during the full mirror. Large enough that 500k rows is a few hundred
# statements, small enough to stay well under Postgres' parameter limit.
BULK_BATCH_SIZE = 500

# Fastq names per lookup when mapping history rows back to mirror rows.
SAMPLE_LOOKUP_CHUNK = 5000

# The stages this app tracks, derived from the enum so the two can never disagree. OCS
# records demand types beyond these, including "transfer", "workflow", and "null", which the dashboard
# has no column for. Export is tracked: it is shown but never submitted.
TRACKED_STAGES = {stage.value for stage in Stage}

# Rows per DELETE when pruning samples that fall outside the configured workflows.
PRUNE_CHUNK = 5000

#: When the stage-status sweep last ran, as opposed to when a row last changed. The two
#: stopped being the same thing once the sweep began skipping unchanged rows. No expiry:
#: losing it means the dashboard falls back to the rows' own timestamps and reads older
#: than it is, which is the safe direction to be wrong in.
LAST_STATUS_SWEEP_KEY = "catalog:last-status-sweep"

#: The dashboard's study filter, cached because unnesting a JSON column over the whole
#: mirror is the most expensive thing on that page. Held here rather than in the web app
#: because this module is what makes it stale: a sync that brings in a new study has to
#: drop it, or the study is in the table and missing from the menu it is filtered by,
#: which reads as the sync having failed.
STUDY_OPTIONS_KEY = "web_ui:study-options"

# OCS statuses that mean "this demand has not reached an outcome yet".
UNFINISHED_STATUSES = frozenset({"IN_PROGRESS", "PENDING", "SUBMITTED"})

# What this app calls a demand that never reached an outcome and that OCS has stopped
# updating. This is not an OCS status. OCS has no such label, so those
# demands sit at IN_PROGRESS forever.
ABANDONED = "ABANDONED"

# How long a demand may sit unfinished before it is read as abandoned rather than running.
# Alignment takes hours, and this matches the fortnight `count_in_progress` already treats
# as the window in-flight work lives in, so nothing genuinely running is ever caught by it.
ABANDONED_AFTER = dt.timedelta(days=14)

# Every field the mirror keeps. Text fields default to "" and numeric ones to None, so a
# metadata entry missing an optional attribute maps cleanly rather than failing.
TEXT_FIELDS = (
    "batch_name",
    "batch_name_from_vendor",
    "sequencing_vendor",
    "organism_common_name",
    "organism_name",
    "library_prep_method_name",
    "library_prep_name",
    "sample_type",
    "cell_prep_type",
    "amplification_name",
    "load_name",
    "alignment_method",
)
NUMBER_FIELDS = (
    "library_prep_method_id",
    "sample_id",
    "cell_capture",
    "amplification_id",
)
LIST_FIELDS = ("sample_names", "studies")

# Every column the sample upsert writes, so the three writers name the same set.
SAMPLE_FIELDS = (*TEXT_FIELDS, *NUMBER_FIELDS, *LIST_FIELDS)

# Vendor text goes straight into fixed-width columns and bulk_create does not validate, so
# it is clipped to the column width here. Otherwise one over-long string raises DataError
# and takes the other 499 rows of its batch with it.
TEXT_FIELD_LIMITS: dict[str, int] = {
    field: cast(int, cast(Any, Sample._meta.get_field(field)).max_length) for field in TEXT_FIELDS
}

#: Said by everything that cannot run without knowing which batches are in scope.
NO_ACTIVE_CONFIG = "No active workflow config, so nothing defines which batches are in scope."


def sync_batch(batch_name_from_vendor: str) -> list[Sample]:
    """Load every fastq sample in a vendor batch, then refresh stage status."""
    entries = dynamodb.get_metadata_by_batch(batch_name_from_vendor)
    samples = _upsert_samples(entries)
    sync_stage_statuses(samples)
    return samples


def sync_fastq_names(fastq_names: list[str]) -> list[Sample]:
    """Load the named fastq samples, then refresh their stage status."""
    entries = dynamodb.get_metadata_by_fastq_names(fastq_names)
    samples = _upsert_samples(entries)
    sync_stage_statuses(samples)
    return samples


def sample_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Map one fastq-metadata entry to local Sample fields."""
    fields: dict[str, Any] = {
        field: _text(entry.get(field), TEXT_FIELD_LIMITS[field]) for field in TEXT_FIELDS
    }
    fields |= {field: _as_int(entry.get(field)) for field in NUMBER_FIELDS}
    fields |= {field: list(entry.get(field) or []) for field in LIST_FIELDS}
    return fields


def _text(value, limit: int) -> str:
    return str(value)[:limit] if value else ""


def _as_int(value):
    # DynamoDB numbers arrive as Decimal, which Django will not store in an integer column.
    return int(value) if value is not None else None


def _upsert_samples(entries: list[dict]) -> list[Sample]:
    """Write fastq metadata entries to the mirror and return the rows."""
    samples = Sample.objects.bulk_create(
        [Sample(fastq_name=entry["fastq_name"], **sample_fields(entry)) for entry in entries],
        update_conflicts=True,
        unique_fields=["fastq_name"],
        update_fields=[*SAMPLE_FIELDS, "synced_at"],
        batch_size=BULK_BATCH_SIZE,
    )
    # A new sample can carry a study nothing else has.
    cache.delete(STUDY_OPTIONS_KEY)
    logger.info("Synced metadata for %d samples", len(samples))
    return samples


def _in_scope(entries: list[dict], batch_prefixes: set[str]) -> list[dict]:
    """Return entries whose vendor batch has a workflow in the manifest."""
    wanted = []
    for entry in entries:
        batch = entry.get("batch_name_from_vendor")
        if not batch or not entry.get("fastq_name"):
            logger.warning("Skipping fastq-metadata entry missing a key attribute: %r", entry)
            continue
        if batch_prefix(batch) in batch_prefixes:
            wanted.append(entry)
    return wanted


def batch_prefix(batch_name_from_vendor: str) -> str:
    """Return the workflow prefix from a vendor batch name, such as MTX from MTX-22028.

    Same rule the submission logic infers a modality with, so the mirror holds exactly the
    batches that could be submitted.
    """
    return batch_name_from_vendor.split("-")[0].upper()


def active_batch_prefixes() -> set[str] | None:
    """Return vendor prefixes in the active manifest, or None without one."""
    from apps.workflow_engine.models import WorkflowConfig

    config = WorkflowConfig.objects.filter(is_active=True).first()
    if config is None:
        return None
    return prefixes_for_workflows(set(config.data["workflows"]))


def sync_all_samples(batch_prefixes: set[str], progress=None) -> dict[str, int]:
    """Load fastq metadata for batches listed in the active manifest."""
    total, skipped = 0, 0
    for page in dynamodb.scan_metadata(batch_prefixes=batch_prefixes):
        wanted = _in_scope(page, batch_prefixes)
        skipped += len(page) - len(wanted)
        total += len(_upsert_samples(wanted))
        if progress:
            progress(total)

    pruned = _prune_out_of_scope(batch_prefixes)
    result = {"mirrored": total, "skipped": skipped, "pruned": pruned}
    logger.info("Mirrored fastq-metadata: %s", result)
    return result


def _prune_out_of_scope(batch_prefixes: set[str]) -> int:
    """Delete mirrored samples outside the active manifest."""
    if not batch_prefixes:
        # exclude(Q()) contributes no WHERE clause, so an empty scope would match and delete
        # every sample. A scope this app cannot name is a config fault, not a
        # licence to empty the mirror.
        raise ValueError("Refusing to prune with no batch prefixes in scope.")

    keep = Q()
    for prefix in batch_prefixes:
        keep |= Q(batch_name_from_vendor__istartswith=f"{prefix}-")

    out_of_scope = Sample.objects.exclude(keep).filter(queue_entries__isnull=True)
    pruned = 0
    while True:
        ids = list(out_of_scope.values_list("id", flat=True)[:PRUNE_CHUNK])
        if not ids:
            return pruned
        Sample.objects.filter(id__in=ids).delete()
        pruned += len(ids)


def sync_all_stage_statuses(batch_prefixes: set[str]) -> dict[str, int]:
    """Refresh stage status for every fastq sample with OCS history.

    Two sweeps and a join, rather than a query per sample: fastq-history says which demand
    ran for each sample and stage, demand-registry says how each demand ended. Both tables
    are small, tens of thousands of rows, which makes doing this on a schedule
    affordable when the catalogue itself has half a million samples.

    Samples with no history keep no StageStatus rows. This represents NOT COMPLETED for
    catalogue samples that predate OCS.
    """
    latest: dict[tuple[str, str], dict] = {}

    def offer(fastq_name: str, stage: str, demand: dict) -> None:
        """Keep the highest ranked demand for a fastq sample and stage."""
        stage = stage.lower()
        # OCS runs demand types this app does not model, such as transfer. Storing
        # rows the dashboard can never show would just be junk in the mirror.
        if stage not in TRACKED_STAGES:
            return
        key = (fastq_name, stage)
        current = latest.get(key)
        if current is None or _demand_rank(demand) > _demand_rank(current):
            latest[key] = demand

    # The registry is the only source for work that has not finished: a demand gains a
    # fastq-history row when it produces output, so IN_PROGRESS, FAILED and ABORTED jobs
    # appear here and nowhere else.
    demands = {}
    for page in dynamodb.scan_demands():
        for demand in page:
            demands[demand["demand_id"]] = demand
            for fastq_name in dynamodb.demand_fastq_names(demand):
                offer(fastq_name, demand["demand_type"], demand)

    # History covers post-alignment and ingest demands that do not name their fastqs. It also
    # confirms completed alignments.
    #
    # It is also the only place the file store id exists: the registry records what a demand
    # was asked to do, history records what it produced. Keyed by demand as well as sample
    # and stage, because a re-ingest leaves two rows for one stage with different outputs,
    # and only the one belonging to the demand that wins below describes it.
    file_store_ids: dict[tuple[str, str, str], str] = {}
    for page in dynamodb.scan_history():
        for row in page:
            demand_type, demand_id = row["demand_type_and_id"].rsplit("#", 1)
            demand = demands.get(demand_id)
            if demand is None:
                continue
            stage = demand_type.lower()
            offer(row["fastq_name"], stage, demand)
            identifier = dynamodb.file_store_id(row)
            if identifier:
                file_store_ids[(row["fastq_name"], stage, demand_id)] = identifier

    fastq_names = {fastq_name for fastq_name, _ in latest}
    sample_ids = _sample_ids(fastq_names)

    # A fastq name in history that is not mirrored is a sample OCS has just begun working
    # on. Fetching those here is what lets a new sample appear within this sweep rather
    # than waiting for the nightly metadata pass.
    discovered = _discover_samples(fastq_names - set(sample_ids), batch_prefixes)
    sample_ids |= discovered

    # What the mirror already says, so the sweep can write only what moved. Reading the
    # table costs one query; writing it costs a new row version per row, every five
    # minutes, whether or not OCS changed anything. This produced about 13M row writes a day to
    # restate values that were already correct.
    existing = _existing_stage_rows()

    statuses, unknown_sample, unchanged = [], 0, 0
    now = dt.datetime.now(dt.UTC)
    for (fastq_name, stage), demand in latest.items():
        sample_id = sample_ids.get(fastq_name)
        if sample_id is None:
            unknown_sample += 1
            continue

        fields = stage_status_fields(
            demand["demand_id"],
            demand,
            file_store_ids.get((fastq_name, stage, demand["demand_id"]), ""),
        )
        # Compared against the row itself rather than a stored high-water mark, so it is
        # self-correcting: anything the mirror does not already say gets written, and a
        # lost write is repaired by the next sweep rather than skipped forever.
        if existing.get((sample_id, stage)) == tuple(fields[name] for name in STAGE_STATUS_FIELDS):
            unchanged += 1
            continue

        statuses.append(
            StageStatus(
                sample_id=sample_id,
                stage=stage,
                **fields,
                # One timestamp for the whole sweep, so the dashboard's freshness clock
                # reads "this sweep" rather than a smear across its twenty seconds.
                synced_at=now,
            )
        )

    _upsert_stage_statuses(statuses)
    reconciled = _reconcile_submitted_failures(demands)

    # "We looked", not "something changed": Max(synced_at) over these rows only advances
    # when a row is written, so a healthy sweep over a quiet pipeline reported the
    # dashboard as hours stale.
    cache.set(LAST_STATUS_SWEEP_KEY, now, timeout=None)

    result = {
        "statuses": len(statuses),
        "unchanged": unchanged,
        "discovered": len(discovered),
        # Left over after discovery: work on a batch outside the configured workflows.
        "out_of_scope": unknown_sample,
        "reconciled": reconciled,
    }
    logger.info("Refreshed stage status: %s", result)
    return result


def _reconcile_submitted_failures(demands: dict[str, dict]) -> int:
    """Mark OmicsHub submissions failed when their OCS demand has failed."""
    from apps.submission_queue.models import QueueEntry

    failed_messages = {
        demand_id: demand.get("message") or "OCS reported this demand as FAILED."
        for demand_id, demand in demands.items()
        if demand.get("status") == "FAILED"
    }
    entries = list(
        QueueEntry.objects.filter(
            demand_id__in=failed_messages,
            status=QueueEntry.Status.SUBMITTED,
        )
    )
    for entry in entries:
        entry.status = QueueEntry.Status.FAILED
        entry.error_message = failed_messages[entry.demand_id]
    QueueEntry.objects.bulk_update(entries, ["status", "error_message"])
    return len(entries)


def _upsert_stage_statuses(statuses: list[StageStatus]) -> None:
    """Write stage statuses, updating the row already there for a (sample, stage)."""
    StageStatus.objects.bulk_create(
        statuses,
        update_conflicts=True,
        unique_fields=["sample", "stage"],
        # synced_at is named here because auto_now only fires on the INSERT half of an
        # upsert, so without it an updated row keeps its first timestamp and the dashboard's
        # freshness clock reports a sweep from a minute ago as days old. The rest come from
        # STAGE_STATUS_FIELDS so a new column cannot be written on insert and then never
        # updated on conflict.
        update_fields=[*STAGE_STATUS_FIELDS, "synced_at"],
        batch_size=BULK_BATCH_SIZE,
    )


def _existing_stage_rows() -> dict[tuple[int, str], tuple]:
    """Return each mirrored stage status as the tuple used for comparison.

    Ordered by STAGE_STATUS_FIELDS so the comparison and the write agree by construction:
    a column added to `stage_status_fields` joins both at once, rather than being written
    but never compared. Those changes would then be invisible to the sweep.
    """
    rows = StageStatus.objects.values_list("sample_id", "stage", *STAGE_STATUS_FIELDS)
    return {(row[0], row[1]): row[2:] for row in rows.iterator(chunk_size=BULK_BATCH_SIZE * 10)}


def _discover_samples(missing: set[str], batch_prefixes: set[str]) -> dict[str, int]:
    """Load fastq samples with OCS history that are missing from the mirror.

    Scoped to the configured workflows for the same reason the metadata sweep is: OCS
    processes batches this app has no workflow for, and they would only be noise here.
    """
    if not missing:
        return {}

    entries = dynamodb.get_metadata_by_fastq_names(sorted(missing))
    wanted = _in_scope(entries, batch_prefixes)
    if not wanted:
        return {}

    samples = _upsert_samples(wanted)
    logger.info("Discovered %d samples new to the mirror", len(samples))
    return {sample.fastq_name: sample.pk for sample in samples}


def _sample_ids(fastq_names: set[str]) -> dict[str, int]:
    """Map fastq names to primary keys in query-sized chunks."""
    names = list(fastq_names)
    mapping: dict[str, int] = {}
    for start in range(0, len(names), SAMPLE_LOOKUP_CHUNK):
        chunk = names[start : start + SAMPLE_LOOKUP_CHUNK]
        mapping.update(Sample.objects.filter(fastq_name__in=chunk).values_list("fastq_name", "id"))
    return mapping


def sync_stage_statuses(samples: list[Sample]) -> None:
    """Refresh each sample's per-stage status from fastq-history and demand-registry.

    fastq-history says which demands ran for a sample; demand-registry supplies each one's
    status, and the demand that best describes the stage wins. See `_demand_rank`.
    """
    if not samples:
        return

    candidates: dict[tuple[int, str], list[str]] = {}
    # Keyed by demand as well, for the same reason the sweep above keys it that way: a
    # re-run leaves two history rows for one stage, each with its own output.
    file_store_ids: dict[tuple[int, str, str], str] = {}

    with ThreadPoolExecutor(max_workers=HISTORY_FETCH_WORKERS) as executor:
        histories = executor.map(dynamodb.get_history, [sample.fastq_name for sample in samples])

    # Every demand in the histories, not just the newest per stage: which one describes the
    # stage depends on its registry status, and the history row does not carry that.
    for sample, history in zip(samples, histories, strict=True):
        for record in history:
            if record["demand_type"] not in TRACKED_STAGES:
                continue
            candidates.setdefault((sample.pk, record["demand_type"]), []).append(record["demand_id"])
            if record.get("file_store_id"):
                key = (sample.pk, record["demand_type"], record["demand_id"])
                file_store_ids[key] = record["file_store_id"]

    demands = dynamodb.get_demands(sorted({demand_id for ids in candidates.values() for demand_id in ids}))

    now = dt.datetime.now(dt.UTC)
    statuses = []
    for (sample_id, stage), candidate_ids in candidates.items():
        # A history row can outlive its demand because the registry is pruned and history is not.
        known = [(demand_id, demands[demand_id]) for demand_id in candidate_ids if demand_id in demands]
        if not known:
            continue
        demand_id, demand = max(known, key=lambda pair: _demand_rank(pair[1]))
        statuses.append(
            StageStatus(
                sample_id=sample_id,
                stage=stage,
                **stage_status_fields(
                    demand_id, demand, file_store_ids.get((sample_id, stage, demand_id), "")
                ),
                synced_at=now,
            )
        )

    # One statement rather than one round trip per row: this path runs behind the
    # dashboard's "Refresh status" button, where a batch can be four hundred samples.
    _upsert_stage_statuses(statuses)

    logger.info("Synced %d stage statuses across %d samples", len(statuses), len(samples))


def stage_status_fields(demand_id: str, demand: dict, file_store_id: str = "") -> dict:
    """Return StageStatus fields for one OCS demand.

    Convert a demand to a row in one place for all three writers, the full sweep, the
    dashboard's targeted refresh, and the submission worker recording what it just sent.
    Built separately, a field added to one path appears after a sweep and vanishes after a
    refresh, which is a horrible thing to debug.

    The demand id is a parameter rather than read off `demand`, because not every source of
    a demand row carries it as a field, and the caller always knows it.

    Do not include `synced_at`. It records when *this app* last looked, not anything
    about the demand, and its writers set it differently.
    """
    return {
        "demand_id": demand_id,
        "status": demand_status(demand),
        "last_update_time": _parse_time(demand["last_update_time"]),
        "started_at": _optional_time(demand, "start_time"),
        "duration_seconds": _duration_seconds(demand),
        "file_store_id": file_store_id,
    }


def submitted_stage_status_fields(demand_id: str) -> dict:
    """Return StageStatus fields for a demand just sent before OCS reports on it.

    SUBMITTED is this app's word for the gap between OCS accepting the command and
    publishing anything about it. The next sweep replaces it with the OCS status.

    Every column is written, including the ones there is nothing to say about yet, because
    a stage can be run twice. Setting only the demand id and status left `started_at`,
    `duration_seconds` and `file_store_id` holding the *previous* demand's values. A
    forced re-run showed a fresh submission carrying the last run's duration and output id
    until the next sweep corrected it.
    """
    return {
        "demand_id": demand_id,
        "status": "SUBMITTED",
        "last_update_time": dt.datetime.now(dt.UTC),
        "started_at": None,
        "duration_seconds": None,
        "file_store_id": "",
    }


#: The columns `stage_status_fields` owns, which the sweep's upsert names as updatable.
#: A test asserts this matches the function's keys, so adding a field there and forgetting
#: it here fails the suite rather than silently never being updated on conflict.
STAGE_STATUS_FIELDS = (
    "demand_id",
    "status",
    "last_update_time",
    "started_at",
    "duration_seconds",
    "file_store_id",
)


def _parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _optional_time(demand: dict, key: str) -> dt.datetime | None:
    """Return a registry timestamp, or None when the registry omits it.

    start_time is absent on demands old enough to predate the field, so this is a real
    case rather than defensive padding.
    """
    value = demand.get(key)
    return _parse_time(value) if value else None


def _duration_seconds(demand: dict) -> int | None:
    """Return the registry run time as an integer.

    DynamoDB numbers arrive as Decimal, which Django will not write to an integer column,
    and a value that is not a number at all (or is negative, which the registry does
    produce for a clock skew) is dropped rather than stored as nonsense.
    """
    raw = demand.get("duration")
    if raw is None:
        return None
    try:
        seconds = int(raw)
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def is_abandoned(demand: dict) -> bool:
    """Return whether a demand stopped updating before it finished.

    OCS never closes a demand whose execution died: SQ_AT0049-1 has an alignment that has
    read IN_PROGRESS since March 2024, message "[STARTING]", while the alignment that
    actually produced its output completed two months earlier. Believing the registry
    literally means the dashboard reports work that is not running, and the planner skips
    the sample as already-in-flight, so it can never be submitted again.
    """
    if demand["status"] not in UNFINISHED_STATUSES:
        return False
    return _parse_time(demand["last_update_time"]) < dt.datetime.now(dt.UTC) - ABANDONED_AFTER


def demand_status(demand: dict) -> str:
    """Return the status to store for a demand, including abandoned status."""
    return ABANDONED if is_abandoned(demand) else demand["status"]


def _demand_rank(demand: dict) -> tuple[int, dt.datetime]:
    """Return the ranking used to choose a demand for a stage.

    Recency alone is not enough. An abandoned demand is newer than the completed one it
    followed and would win on time, so it is ranked below every demand that still says
    something. It describes the stage only when no other demand does.

    Compared as a parsed datetime, not as the raw string: the registry emits both "…Z" and
    "…+00:00", which sort against each other by spelling rather than by instant, so a
    mixture would hand the stage to the wrong demand.
    """
    return (0 if is_abandoned(demand) else 1, _parse_time(demand["last_update_time"]))
