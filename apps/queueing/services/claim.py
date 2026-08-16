"""Claim the next queue entry and balance submissions across users.

OCS capacity is shared, so a strict global FIFO would let one user's batch of 500 samples
block everyone else for a day. Instead the user who has waited longest since their own
last attempt goes next; a user who has never been served goes before anyone who has.
Within a user it is oldest-first.

The turn is taken on the attempt, not on the success. Ranking on `submitted_at` starved
everyone else whenever one user's entries were failing: a failure never advanced their
key, so they stayed at the front and were served again immediately.

The claimed row is moved to SUBMITTING and committed before the CLI is called, so the
entry is off the queue while it is in flight and a second worker cannot pick it up.
"""

from __future__ import annotations

import datetime as dt

from django.db import transaction
from django.db.models import Max, Min
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.queueing.models import QueueEntry

# Sorts users the worker has never reached ahead of everyone else.
NEVER_SERVED = dt.datetime.min.replace(tzinfo=dt.UTC)


def claim_next_entry() -> QueueEntry | None:
    """Claim one pending entry, mark it SUBMITTING, or return None without one."""
    with transaction.atomic():
        pending = QueueEntry.objects.filter(status=QueueEntry.Status.PENDING)

        oldest_pending_by_user = dict(
            pending.values("requested_by")
            .annotate(oldest=Min("created_at"))
            .values_list("requested_by", "oldest")
        )
        if not oldest_pending_by_user:
            return None

        last_attempt_by_user = dict(
            QueueEntry.objects.filter(requested_by__in=oldest_pending_by_user)
            .values("requested_by")
            .annotate(last=Max(Coalesce("claimed_at", "submitted_at")))
            .values_list("requested_by", "last")
        )

        user_order = sorted(
            oldest_pending_by_user,
            key=lambda user_id: (
                last_attempt_by_user.get(user_id) or NEVER_SERVED,
                oldest_pending_by_user[user_id],
            ),
        )

        for user_id in user_order:
            entry = (
                pending.filter(requested_by_id=user_id)
                .order_by("created_at")
                .select_for_update(skip_locked=True)
                .first()
            )
            if entry is not None:
                entry.status = QueueEntry.Status.SUBMITTING
                entry.claimed_at = timezone.now()
                entry.save(update_fields=["status", "claimed_at"])
                return entry

        return None


def record_submission(entry: QueueEntry, demand_id: str) -> None:
    entry.status = QueueEntry.Status.SUBMITTED
    entry.demand_id = demand_id
    entry.submitted_at = timezone.now()
    entry.save(update_fields=["status", "demand_id", "submitted_at"])


def record_stranded(entry: QueueEntry, message: str) -> None:
    """Mark a submission with an unknown outcome as STRANDED."""
    entry.status = QueueEntry.Status.STRANDED
    entry.error_message = message
    entry.save(update_fields=["status", "error_message"])


def record_failure(entry: QueueEntry, message: str) -> None:
    entry.status = QueueEntry.Status.FAILED
    entry.error_message = message
    entry.save(update_fields=["status", "error_message"])
