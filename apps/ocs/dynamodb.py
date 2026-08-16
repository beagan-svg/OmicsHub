"""Read OCS fastq metadata, history, and demand data from DynamoDB.

OCS owns three tables this backend reads (names are prefixed with the environment base,
so "prod" gives "prod-fastq-metadata"):

    fastq-metadata    PK fastq_name                     sample metadata
    fastq-history     PK fastq_name, SK demand_type_and_id   which demands ran for a sample
    demand-registry   PK demand_id                      demand status and timings

A sample's stage status is the join of the last two: fastq-history says which demand ran
for a stage, demand-registry says how that demand ended. Reading them directly replaces
the `ocs fastqs list *-results` and `ocs core gwo demand get-status` calls the previous
app shelled out to, and `count_in_progress` replaces `ocs core gwo demand list-demands`.

Table and index names mirror gcs_core.models.db.{tx,gwo}.constants; index names follow
aibs_informatics_core's DBIndexNameEnum.from_name_and_key, which hyphenates key names.
"""

from __future__ import annotations

import datetime as dt
import re
import threading
import time
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key
from django.conf import settings

FASTQ_METADATA_TABLE = "fastq-metadata"
FASTQ_HISTORY_TABLE = "fastq-history"
DEMAND_REGISTRY_TABLE = "demand-registry"

FASTQ_METADATA_BATCH_INDEX = f"{FASTQ_METADATA_TABLE}-batch-name-from-vendor-index"
DEMAND_REGISTRY_TYPE_INDEX = f"{DEMAND_REGISTRY_TABLE}-demand-type-start-time-index"

# demand-registry is partitioned by demand_type and sorted by start_time, so counting
# in-flight demands needs a lower bound on start_time. Two weeks matches the default
# window GWORegistry.list_demands uses and comfortably covers any running job.
IN_PROGRESS_LOOKBACK = dt.timedelta(days=14)

# DynamoDB caps BatchGetItem at 100 keys per request.
BATCH_GET_CHUNK = 100

# Keys come back unprocessed when the table throttles, so retrying them immediately is
# how a throttled table gets hammered. Doubles per consecutive retry, up to the cap.
UNPROCESSED_BACKOFF = 0.05
UNPROCESSED_BACKOFF_CAP = 5.0

# A GFS path is the "gfs://" scheme plus a file store id, which gcs_core defines as the
# sha1 of the S3 URI — forty lowercase hex characters. Matching that shape rather than
# just stripping the scheme keeps a malformed row out of the mirror instead of storing a
# string nobody can paste into OCS tooling.
GFS_PATH = re.compile(r"^gfs://([0-9a-f]{40})$")

# One boto3 resource per thread — see _resource().
_local = threading.local()


def reset_resource_cache() -> None:
    """Clear this thread's cached DynamoDB resource.

    Exists for tests: they swap boto3.Session for a fake, and a resource cached by an
    earlier test would otherwise outlive the patch and quietly serve the real client.
    It clears only the calling thread's resource, so it is not a way to pick up a settings
    change across a running worker pool.
    """
    _local.resource = None


def _resource():
    """Return the calling thread's DynamoDB resource.

Credentials come from boto3's own chain. Use a named profile when AWS_PROFILE is set,
    otherwise the environment or the instance role. Nothing credential-shaped is read from
    Django settings or stored by this project.

    Cached per thread rather than per call. boto3 sessions and resources are documented as
    not thread-safe, so one shared across the history-fetch pool is wrong, and a fresh one
    per call re-parses the config and credential files on each of the thousands of requests
    a full sweep makes. A thread-local gives each worker exactly one.
    """
    resource = getattr(_local, "resource", None)
    if resource is None:
        session = boto3.Session(profile_name=settings.AWS_PROFILE or None)
        resource = session.resource("dynamodb", region_name=settings.OCS_AWS_REGION)
        _local.resource = resource
    return resource


def _table(name: str):
    return _resource().Table(f"{settings.OCS_ENV_BASE}-{name}")


def _query_all(table, **kwargs) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    while True:
        response = table.query(**kwargs)
        items.extend(response["Items"])
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key


def _batch_get(name: str, keys: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not keys:
        return []

    resource = _resource()
    table_name = f"{settings.OCS_ENV_BASE}-{name}"
    items: list[dict[str, Any]] = []

    # A repeated key makes DynamoDB reject the whole request with ValidationException, and
    # demand ids gathered across history rows do repeat.
    unique = list({tuple(sorted(key.items())): key for key in keys}.values())

    for start in range(0, len(unique), BATCH_GET_CHUNK):
        request = {table_name: {"Keys": unique[start : start + BATCH_GET_CHUNK]}}
        delay = UNPROCESSED_BACKOFF
        while request:
            response = resource.batch_get_item(RequestItems=request)
            items.extend(response["Responses"].get(table_name, []))
            request = response.get("UnprocessedKeys") or None
            if request:
                time.sleep(delay)
                delay = min(delay * 2, UNPROCESSED_BACKOFF_CAP)

    return items


def get_metadata_by_fastq_names(fastq_names: list[str]) -> list[dict[str, Any]]:
    """Return fastq-metadata entries for the given fastq names.

Names without an OCS entry are absent from the result; the caller decides
    what an unknown sample means.
    """
    return _batch_get(FASTQ_METADATA_TABLE, [{"fastq_name": name} for name in fastq_names])


def scan_metadata(batch_prefixes: set[str] | None = None, page_size: int = 1000):
    """Yield fastq-metadata entries one page at a time.

    A generator rather than a list: the table holds hundreds of thousands of entries, and
    the caller writes each page to the database before asking for the next one.

    `batch_prefixes` pushes a begins_with filter to DynamoDB so unwanted batches are never
sent over the wire. It narrows transfer, not cost. A filtered scan still reads the
whole table, and the caller re-checks the prefix because begins_with cannot
    express "the part before the first hyphen".
    """
    kwargs = {}
    if batch_prefixes:
        prefixes = sorted(batch_prefixes)
        condition = Attr("batch_name_from_vendor").begins_with(prefixes[0])
        for prefix in prefixes[1:]:
            condition |= Attr("batch_name_from_vendor").begins_with(prefix)
        kwargs["FilterExpression"] = condition

    yield from _scan(FASTQ_METADATA_TABLE, page_size, **kwargs)


def scan_history(page_size: int = 1000):
    """Yield fastq-history rows with the demand, fastq sample, and timestamp.

    The table is small enough (tens of thousands of rows) to sweep whole, which is what
makes stage status for the entire catalogue affordable. The alternative is one query
    per sample.
    """
    yield from _scan(
        FASTQ_HISTORY_TABLE,
        page_size,
        # The two GFS attributes are what `file_store_id` reads — see that function for
        # why both are needed to name a single stage's output.
        ProjectionExpression=(
            "fastq_name,demand_type_and_id,last_update_time,fastq_gfs_path,input_output_gfs_pairs"
        ),
    )


def file_store_id(history_row: dict[str, Any]) -> str:
    """Return the file store id produced by one stage, or an empty string when unclear.

    This is the id `ocs gfs` commands take and the CLI prints as `file_store_id`: the sha1
    half of the row's output GFS path.

    Alignment and post-alignment rows carry exactly one output, so that is the answer. An
    ingest row does not: one ingest demand transfers a whole run, and its outputs list holds
a path per fastq in it, up to fifteen in production. The one belonging to *this* sample
    is `fastq_gfs_path`, the GFS path of its fastq set, which is why the row carries it and
    why every downstream stage names it as an input. So: prefer `fastq_gfs_path` when the
    row produced it, fall back to a lone output, and give nothing when a row has several
outputs and no way to identify this sample. A wrong id is worse than a blank cell.
    """
    outputs = {
        path for pair in history_row.get("input_output_gfs_pairs") or [] for path in pair.get("outputs") or []
    }
    fastq_gfs_path = history_row.get("fastq_gfs_path")
    if fastq_gfs_path in outputs:
        return _file_store_id(fastq_gfs_path)
    if len(outputs) == 1:
        return _file_store_id(next(iter(outputs)))
    return ""


def _file_store_id(gfs_path: str) -> str:
    match = GFS_PATH.match(gfs_path or "")
    return match.group(1) if match else ""


def scan_demands(page_size: int = 1000):
    """Yield demand-registry rows with the id, type, status, update time, and fastq names.

    FASTQ_NAMES is pulled out of the submitted request because it is the only place a
    demand says which samples it is for. It is what makes an in-flight or failed job
    visible: fastq-history only gains a row once a demand has produced output, so
    IN_PROGRESS, FAILED and ABORTED work exists nowhere else.

Only alignment demands carry it. Post-alignment references alignment outputs, and ingest
references neither, so those two stages are known from history alone.
    """
    yield from _scan(
        DEMAND_REGISTRY_TABLE,
        page_size,
        # start_time and duration are what let the dashboard say how long a stage took.
        # The registry computes duration itself (seconds, as a DynamoDB Number), so it is
        # read rather than derived here — deriving it from the two timestamps would give a
        # different answer for any demand OCS retried or backdated.
        ProjectionExpression=(
            "demand_id,#s,demand_type,start_time,#d,last_update_time,"
            "#r.execution_parameters.params.FASTQ_NAMES"
        ),
        # "status", "request" and "duration" are all DynamoDB reserved words.
        ExpressionAttributeNames={"#s": "status", "#r": "request", "#d": "duration"},
    )


def demand_fastq_names(demand: dict[str, Any]) -> list[str]:
    """Return fastq names from a demand request such as `FASTQ_SET_1=NW_TX0194-1`."""
    raw = demand.get("request", {}).get("execution_parameters", {}).get("params", {}).get("FASTQ_NAMES", "")
    return [pair.split("=", 1)[1] for pair in raw.split(",") if "=" in pair]


def _scan(table_name: str, page_size: int, **kwargs):
    table = _table(table_name)
    kwargs["Limit"] = page_size
    while True:
        response = table.scan(**kwargs)
        yield response["Items"]
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return
        kwargs["ExclusiveStartKey"] = last_key


def get_metadata_by_batch(batch_name_from_vendor: str) -> list[dict[str, Any]]:
    """Return every fastq-metadata entry in a vendor batch."""
    return _query_all(
        _table(FASTQ_METADATA_TABLE),
        IndexName=f"{settings.OCS_ENV_BASE}-{FASTQ_METADATA_BATCH_INDEX}",
        KeyConditionExpression=Key("batch_name_from_vendor").eq(batch_name_from_vendor),
    )


def get_history(fastq_name: str) -> list[dict[str, str]]:
    """Return every demand recorded for a fastq name.

    The sort key packs the two values together as "<demand_type>#<demand_id>", so it is
    split back apart here. Demand types are the lowercase DemandType values: "ingest",
    "align", "post-align".
    """
    entries = _query_all(
        _table(FASTQ_HISTORY_TABLE),
        KeyConditionExpression=Key("fastq_name").eq(fastq_name),
    )

    history = []
    for entry in entries:
        demand_type, demand_id = entry["demand_type_and_id"].rsplit("#", 1)
        history.append(
            {
                "demand_type": demand_type.lower(),
                "demand_id": demand_id,
                "last_update_time": entry["last_update_time"],
                "file_store_id": file_store_id(entry),
            }
        )
    return history


def get_demands(demand_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Return demand-registry entries keyed by demand id."""
    entries = _batch_get(DEMAND_REGISTRY_TABLE, [{"demand_id": demand_id} for demand_id in demand_ids])
    return {entry["demand_id"]: entry for entry in entries}


def count_in_progress(demand_type: str) -> int:
    """Count OCS demands of one type with IN_PROGRESS status.

    This is the capacity check the queue worker gates submissions on.
    """
    since = (dt.datetime.now(dt.UTC) - IN_PROGRESS_LOOKBACK).isoformat().replace("+00:00", "Z")
    table = _table(DEMAND_REGISTRY_TABLE)
    kwargs: dict[str, Any] = {
        "IndexName": f"{settings.OCS_ENV_BASE}-{DEMAND_REGISTRY_TYPE_INDEX}",
        "KeyConditionExpression": Key("demand_type").eq(demand_type) & Key("start_time").gte(since),
        "FilterExpression": Attr("status").eq("IN_PROGRESS"),
        "Select": "COUNT",
    }

    count = 0
    while True:
        response = table.query(**kwargs)
        count += response["Count"]
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return count
        kwargs["ExclusiveStartKey"] = last_key
