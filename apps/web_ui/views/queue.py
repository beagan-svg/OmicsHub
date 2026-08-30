"""Render queue pages and actions."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.submission_queue import tasks
from apps.submission_queue.models import QueueEntry

from .common import QUEUED_STATUSES, _owned


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
    """Pause or resume the requesting user's pending queue entries."""
    request.user.queue_paused = not request.user.queue_paused
    request.user.save(update_fields=["queue_paused"])
    state = "paused" if request.user.queue_paused else "resumed"
    messages.success(request, f"Your queue is {state}.")
    return redirect("web_ui:queue")


@login_required
@require_POST
def delete_queue_entry(request, pk):
    """Delete the requesting user's pending queue entry without affecting OCS."""
    entry = get_object_or_404(_owned(request), pk=pk)
    deleted, _ = QueueEntry.objects.filter(pk=entry.pk, status=QueueEntry.Status.PENDING).delete()
    if deleted:
        messages.success(request, f"Deleted {entry.sample.fastq_name} from the queue.")
    else:
        messages.error(request, f"{entry.sample.fastq_name} is already being submitted.")
    return redirect("web_ui:queue")
