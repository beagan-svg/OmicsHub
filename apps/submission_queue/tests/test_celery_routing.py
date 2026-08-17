"""Every scheduled task must land on a queue a worker is actually listening to.

The deployment runs two workers, `-Q default` and `-Q submissions`. Celery's own default
queue is named "celery", so dropping `CELERY_TASK_DEFAULT_QUEUE` publishes every unrouted
task to a queue nobody consumes: beat keeps reporting "Sending due task", the messages pile
up in Redis, and the sweeps simply stop running with nothing in any log to say so.
"""

from __future__ import annotations

from celery import current_app
from django.conf import settings

# The queues used by the workers. See the README's run commands.
CONSUMED_QUEUES = {"default", "submissions"}


def queue_for(task_name: str) -> str:
    return current_app.amqp.router.route({}, task_name)["queue"].name


def test_every_scheduled_task_is_consumed_by_a_worker():
    for name, entry in settings.CELERY_BEAT_SCHEDULE.items():
        queue = queue_for(entry["task"])
        assert queue in CONSUMED_QUEUES, f"{name} routes to {queue!r}, which no worker consumes"


def test_submissions_are_serialised_onto_their_own_queue():
    """One worker, one submission at a time , the whole pacing design rests on it."""
    assert queue_for("apps.submission_queue.tasks.process_next_queue_entry") == "submissions"
