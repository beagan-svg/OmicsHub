"""Submit queued alignment and post-alignment commands one at a time."""

from __future__ import annotations

import datetime as dt
import logging
import math

from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.ocs_integration import cli, dynamodb
from apps.sample_catalog import ocs_sync as sync
from apps.sample_catalog.models import StageStatus
from apps.submission_queue.models import QueueEntry
from apps.submission_queue.queue_claiming import (
    claim_next_entry,
    record_failure,
    record_submission,
)
from apps.workflow_engine.models import WorkflowConfig

logger = logging.getLogger(__name__)

# The demand types that count against the OCS job limit.
LIMITED_DEMAND_TYPES = ("align", "post-align")

# Set when OCS is full, and left to expire after `job_settings.poll_interval_hours`. While
# it is set every run returns immediately, so the queue waits without re-counting OCS on
# every beat tick and without stacking up retries.
CAPACITY_HOLD_KEY = "submission_queue:capacity-hold"

# Set for `spacing` seconds after each submission. Every caller checks it, which is what
# makes the config's spacing hold against beat's own minute tick.
SPACING_HOLD_KEY = "submission_queue:spacing-hold"

# Refreshed on every task run and read by the health endpoint. A stale key means the
# scheduler, broker, or submissions worker is not moving queue entries.
WORKER_HEARTBEAT_KEY = "submission_queue:submissions-worker-seen"
WORKER_HEARTBEAT_TTL = 300


def _hold_for_spacing(seconds: int) -> None:
    """Hold submissions for `seconds`."""
    if seconds:
        cache.set(
            SPACING_HOLD_KEY,
            timezone.now() + dt.timedelta(seconds=seconds),
            timeout=seconds,
        )


def hold_remaining_seconds(key: str) -> int:
    """Return the seconds remaining on a submission hold."""
    expiry = cache.get(key)
    if not isinstance(expiry, dt.datetime):
        return 0
    return max(0, math.ceil((expiry - timezone.now()).total_seconds()))


@shared_task
def process_next_queue_entry():
    """Submit the next queued command, then schedule the next worker run."""
    # Before any early return: reaching this line at all is the proof the health endpoint
    # reads. Beat published, the broker delivered, and this worker consumed the task.
    cache.set(WORKER_HEARTBEAT_KEY, timezone.now().isoformat(), timeout=WORKER_HEARTBEAT_TTL)

    config_entry = WorkflowConfig.objects.filter(is_active=True).first()
    if config_entry is None:
        logger.warning("No active workflow config; not submitting anything")
        return

    job_settings = config_entry.data["job_settings"]

    # Beat runs this every minute; an empty queue should not cost a DynamoDB query.
    if not QueueEntry.objects.filter(status=QueueEntry.Status.PENDING).exists():
        return

    # Still inside the window a previous run opened after finding OCS full. Returning here
    # is what makes `poll_interval_hours` mean something: without it beat's own 60-second
    # tick re-counts OCS every minute no matter what the config asks for.
    if cache.get(CAPACITY_HOLD_KEY):
        return

    # The previous submission's spacing has not elapsed yet.
    if cache.get(SPACING_HOLD_KEY):
        return

    in_progress = sum(dynamodb.count_in_progress(demand_type) for demand_type in LIMITED_DEMAND_TYPES)
    if in_progress >= job_settings["limit"]:
        # A hold with a TTL, rather than a self-scheduled retry. The retry was additive:
        # beat kept calling this every minute while the limit held, and each call queued
        # another delayed task, so an hour at the limit left ~60 of them. They all came due
        # at once when capacity freed, and because each was already queued, none of them
        # waited for the `spacing` countdown below. The config asks for 180 seconds
        # between alignments and would have got none, at the worst possible moment.
        hold_for = job_settings.get("poll_interval_hours", 1) * 3600
        cache.set(
            CAPACITY_HOLD_KEY,
            timezone.now() + dt.timedelta(seconds=hold_for),
            timeout=hold_for,
        )
        logger.info(
            "OCS has %d jobs in progress (limit %d); holding off for %s seconds",
            in_progress,
            job_settings["limit"],
            hold_for,
        )
        return

    entry = claim_next_entry()
    if entry is None:
        return

    try:
        demand_id = cli.submit(entry.command_args)
    except cli.OCSSubmissionError as error:
        logger.warning("OCS submission failed for %s: %s", entry, error)
        record_failure(entry, str(error))
        process_next_queue_entry.delay()
        return
    except Exception:
        # Not a refusal from OCS but a fault on our side. Record the failure so the entry
        # is visible for review, then let the exception reach the worker error log.
        record_failure(entry, "Submission failed unexpectedly. Check the worker log.")
        raise

    _hold_for_spacing(entry.spacing)
    # One transaction: an entry recorded as SUBMITTED with no matching StageStatus reads on
    # the dashboard as a stage nobody has started, until the next sweep says otherwise.
    with transaction.atomic():
        record_submission(entry, demand_id)
        # Through the same module the sweeps write with, so all three writers of this table
        # agree on what a row contains. See `sync.submitted_stage_status_fields` for why
        # every column is written rather than just the two that changed.
        StageStatus.objects.update_or_create(
            sample=entry.sample,
            stage=entry.stage,
            defaults=sync.submitted_stage_status_fields(demand_id),
        )
    logger.info("Submitted %s as demand %s", entry, demand_id)

    process_next_queue_entry.apply_async(countdown=entry.spacing)
