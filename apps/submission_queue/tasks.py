"""Submit queued alignment and post-alignment commands.

One entry is submitted per task run, and the run queues the next one. Two things pace it,
and both are expressed as a cache key with a TTL rather than as a delay on a queued task:

* the job limit from the config, checked against the demands OCS currently has in
  progress. At the limit nothing is claimed and a capacity hold is set for
  `poll_interval_hours`, so jobs wait rather than being dropped;
* the `spacing` on the command config, held after each submission.

A hold rather than a countdown because this task has three callers: beat every 60
seconds, its own follow-up, and the "process now" button. A countdown only paces the
one that scheduled it. Spacing of 180 seconds against a 60-second beat tick meant beat
claimed and submitted twice more before the countdown ever came due, so the pacing the
config asks for was not happening at all. A hold is checked by whoever arrives.

The same reasoning is why the limit branch does not queue its own retry: a retry queued
per beat tick accumulates while the limit holds, and every accumulated task is already
past its countdown when capacity frees. That would submit the whole backlog at once, in
the moment spacing matters most.

Both only mean something if submissions are serialized, which is why this task is routed
to the `submissions` queue and that queue is run with a single worker process.

`acks_late` is deliberately left off. Celery's default acknowledges a task when it starts,
so a worker killed mid-submission does *not* get the task redelivered. That is what we
want, because a redelivered submission could run the same alignment twice. The cost is an
entry stuck in SUBMITTING, and `reconcile_stranded_submissions` is what answers for it.
"""

from __future__ import annotations

import datetime as dt
import logging
import math

from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.ocs_integration import cli, dynamodb
from apps.sample_catalog.models import StageStatus
from apps.sample_catalog.services import sync
from apps.submission_queue.models import QueueEntry
from apps.submission_queue.services.claim import (
    claim_next_entry,
    record_failure,
    record_stranded,
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

# How long an entry may sit in SUBMITTING before it is treated as abandoned. Comfortably
# longer than OCS_CLI_TIMEOUT, so a slow submission is never mistaken for a dead worker.
STRANDED_AFTER = dt.timedelta(minutes=30)

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
    except cli.OCSSubmissionUncertain as error:
        # The command may already be running at OCS. STRANDED keeps it out of the admin's
        # bulk requeue, so recovering it takes a person who has checked. Spaced like a
        # submission for the same reason: it may well have been one.
        logger.exception("Submission outcome unknown for %s", entry)
        record_stranded(entry, str(error))
        _hold_for_spacing(entry.spacing)
        process_next_queue_entry.delay()
        return
    except cli.OCSSubmissionError as error:
        logger.warning("OCS refused %s: %s", entry, error)
        record_failure(entry, str(error))
        # A refused submission did not consume OCS capacity, so move straight on.
        process_next_queue_entry.delay()
        return
    except Exception:
        # Not a refusal from OCS but a fault on our side. Record it so the entry does not
        # sit in SUBMITTING until reconcile picks it up, then let it reach the error log
        # rather than being reported to the user as an ordinary failed job.
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


@shared_task
def reconcile_stranded_submissions():
    """Move abandoned SUBMITTING entries to STRANDED."""
    cutoff = timezone.now() - STRANDED_AFTER
    stranded = QueueEntry.objects.filter(status=QueueEntry.Status.SUBMITTING, claimed_at__lt=cutoff)

    count = stranded.update(
        status=QueueEntry.Status.STRANDED,
        error_message=(
            "The worker stopped while submitting this job. Check OCS for a demand covering "
            "this sample and stage: if one exists, record it and close this entry; if not, "
            "set the status back to PENDING to submit it again."
        ),
    )
    if count:
        logger.warning("Marked %d abandoned submissions STRANDED", count)
    return count
