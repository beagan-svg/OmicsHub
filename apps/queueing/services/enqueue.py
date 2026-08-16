"""Create queue entries from a confirmed submission plan."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import IntegrityError, transaction

from apps.queueing.models import QueueEntry
from apps.queueing.services.planning import Plan, PlannedEntry


@dataclass(frozen=True)
class EnqueueResult:
    created: list[QueueEntry]
    already_queued: list[PlannedEntry]


def enqueue(
    *,
    plan: Plan,
    user,
    notify_email: str,
    forced: bool = False,
    batch_processing: bool = False,
) -> EnqueueResult:
    """Create one pending queue entry for each planned stage.

    A sample already waiting for the same stage is reported back rather than queued
twice. The usual cause is a second confirmation of the same plan.

    The read and the writes are one transaction, and each write is its own savepoint: two
    confirms landing together both see an empty queue, and `one_pending_entry_per_sample_stage`
    is what actually decides. The loser of that race is reported as already queued, which
is what it is, rather than raising an error that the user would see as a failed submission of
    jobs that are in fact queued.
    """
    created = []
    already_queued = []

    with transaction.atomic():
        pending_keys = set(
            QueueEntry.objects.filter(
                status=QueueEntry.Status.PENDING,
                sample__in=[entry.sample for entry in plan.entries],
            ).values_list("sample_id", "stage")
        )

        for entry in plan.entries:
            if (entry.sample.pk, entry.stage) in pending_keys:
                already_queued.append(entry)
                continue
            row = QueueEntry(
                sample=entry.sample,
                stage=entry.stage,
                requested_by=user,
                modality=entry.modality,
                modality_source=entry.modality_source,
                notify_email=notify_email,
                batch_processing=batch_processing,
                forced=forced,
                command_args=entry.command_args,
                command=entry.command,
                spacing=entry.spacing,
            )
            try:
                with transaction.atomic():
                    row.save()
            except IntegrityError:
                already_queued.append(entry)
            else:
                created.append(row)

    return EnqueueResult(created=created, already_queued=already_queued)
