"""Create queue entries from a confirmed submission plan."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import IntegrityError, transaction

from apps.submission_queue.models import QueueEntry
from apps.submission_queue.services.planning import Plan, PlannedEntry


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
    """Create one pending queue entry for each planned stage."""
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
