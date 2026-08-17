"""Refresh the local mirror from OCS."""

from __future__ import annotations

import logging

from celery import shared_task
from django.core.cache import cache

from apps.sample_catalog.services import sync

logger = logging.getLogger(__name__)

#: Held for the length of a stage-status sweep so a slow one cannot run alongside itself.
SWEEP_LOCK_KEY = "catalog:stage-status-sweep"

#: Matches CELERY_TASK_TIME_LIMIT: a worker killed at the limit never reaches its `finally`,
#: so the lock has to expire on its own or the sweep stops running until someone notices.
SWEEP_LOCK_TIMEOUT = 900


# acks_late because the sweep is idempotent. It rereads both OCS tables from scratch and
# writes only what moved, so a worker lost mid-run should have its message redelivered
# rather than silently dropped.
@shared_task(acks_late=True)
def sync_all_stage_statuses():
    """Refresh stage status for every fastq sample with OCS history.

    Replaces polling only the samples already known to be running: that could refresh a
    job in flight but could never discover one, so a sample whose alignment started
    outside this app stayed NOT COMPLETED forever. Both source tables are small enough to
    sweep whole in seconds, so this covers everything in scope and picks up samples that
    are new to the mirror on the way.

    Beat fires this every five minutes against a fifteen-minute time limit, so a sweep
    slowed by a large catalogue would otherwise overlap itself, with both copies writing.
    """
    if not cache.add(SWEEP_LOCK_KEY, True, timeout=SWEEP_LOCK_TIMEOUT):
        logger.info("Stage-status sweep still running; skipping this tick")
        return None
    try:
        batch_prefixes = sync.active_batch_prefixes()
        if batch_prefixes is None:
            logger.warning(sync.NO_ACTIVE_CONFIG)
            return None
        return sync.sync_all_stage_statuses(batch_prefixes=batch_prefixes)
    finally:
        cache.delete(SWEEP_LOCK_KEY)


@shared_task(acks_late=True)
def sync_all_metadata():
    """Load new fastq-metadata entries into the local mirror.

    Scoped to the batches the active config has workflows for; without a config there is
    nothing to scope by, so the sweep is skipped rather than pulling the whole table and
    rather than reaching the prune with an empty scope, which means "delete everything".
    """
    batch_prefixes = sync.active_batch_prefixes()
    if batch_prefixes is None:
        logger.warning(sync.NO_ACTIVE_CONFIG)
        return None
    return sync.sync_all_samples(batch_prefixes=batch_prefixes)
