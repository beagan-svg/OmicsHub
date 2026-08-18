"""Check required services and worker readiness."""

from celery import current_app
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse

from apps.submission_queue.tasks import WORKER_HEARTBEAT_KEY, WORKER_HEARTBEAT_TTL
from apps.workflow_engine.models import WorkflowConfig

OK = "ok"

# Broad `except Exception`: a health check reports a failure, it does not raise one.


def _check_database():
    try:
        connection.ensure_connection()
    except Exception as error:
        return f"unavailable: {error.__class__.__name__}"
    return OK


def _check_broker():
    try:
        # The context manager releases the connection. Without it every health check
        # leaves a broker socket open, and a monitor polling this endpoint would leak one
        # per request.
        with current_app.connection() as broker:
            broker.ensure_connection(max_retries=0)
    except Exception as error:
        return f"unavailable: {error.__class__.__name__}"
    return OK


# Namespaced and short-lived. The value is never read by anything but the check itself.
CACHE_PROBE_KEY = "healthz:probe"
CACHE_PROBE_TTL = 10


def _check_cache():
    """Check that the cache can write and read a value."""
    try:
        cache.set(CACHE_PROBE_KEY, OK, CACHE_PROBE_TTL)
        if cache.get(CACHE_PROBE_KEY) != OK:
            return "unavailable: value did not survive a write and read"
    except Exception as error:
        return f"unavailable: {error.__class__.__name__}"
    return OK


def _check_submissions_worker():
    """Check that the submission task has run within the expected interval."""
    try:
        seen = cache.get(WORKER_HEARTBEAT_KEY)
    except Exception as error:
        return f"unknown: {error.__class__.__name__}"

    if not seen:
        minutes = WORKER_HEARTBEAT_TTL // 60
        return (
            f"no submission run in the last {minutes} minutes. "
            "Check the scheduler and the OCS submission worker."
        )
    return OK


def _check_workflow_config():
    try:
        exists = WorkflowConfig.objects.filter(is_active=True).exists()
    except Exception as error:
        return f"unknown: {error.__class__.__name__}"
    return OK if exists else "no active config. Upload and activate one."


def health(request):
    required = {
        "database": _check_database(),
        "cache": _check_cache(),
        "broker": _check_broker(),
    }
    # The heartbeat lives in the cache, so with the cache down its absence says nothing
    # about the worker.
    required["submissions_worker"] = (
        _check_submissions_worker() if required["cache"] == OK else "unknown: cache unavailable"
    )
    checks = {**required, "workflow_config": _check_workflow_config()}
    ready = all(status == OK for status in required.values())
    return JsonResponse(
        {"status": OK if ready else "not ready", "checks": checks}, status=200 if ready else 503
    )
