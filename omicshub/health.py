"""Check database, cache, broker, worker, and workflow manifest readiness.

The backend cannot do any work without the database, the cache, the Celery broker, or a
worker actually consuming the submissions queue, so those four decide the status code. An
active workflow config is reported alongside them because its absence is worth seeing, but
it is a setup step rather than an outage. Gating readiness on it would stop a healthy
deployment from ever entering service.

The worker check is the one that earns this endpoint. A broker that accepts a job and a
queue nobody consumes look identical from the outside: entries pile up as PENDING, every
page renders, nothing errors, and no submission ever reaches OCS. That state held here for
an hour. Three dead workers and a green health check caused exactly the failure this
was supposed to name. It reads a heartbeat rather than polling the workers; see
`_check_submissions_worker` for why the direct question could not be trusted.
"""

from celery import current_app
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse

from apps.queueing.tasks import WORKER_HEARTBEAT_KEY, WORKER_HEARTBEAT_TTL
from apps.workflows.models import WorkflowConfig

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
    """Check that the cache can write and read a value.

    The cache is a hard dependency of the submission worker: the OCS job-limit hold and
    the per-config spacing hold both live there, and with the cache gone the worker either
    stops submitting or loses the pacing that keeps it inside the limit. That makes it a
    readiness dependency, not a nice-to-have.

    Written and read back rather than pinged, because the failure that matters is a cache
that accepts connections and refuses writes. A Redis that has hit `maxmemory` with a
    no-eviction policy, or one failed over to a read-only replica. Both answer a ping.
    """
    try:
        cache.set(CACHE_PROBE_KEY, OK, CACHE_PROBE_TTL)
        if cache.get(CACHE_PROBE_KEY) != OK:
            return "unavailable: value did not survive a write and read"
    except Exception as error:
        return f"unavailable: {error.__class__.__name__}"
    return OK


def _check_submissions_worker():
    """Check that the submission task has run recently.

    Reads the heartbeat `process_next_queue_entry` refreshes on every run rather than
    broadcasting to the workers. `inspect().active_queues()` answers the narrower question
    "is a consumer attached", and it answers it unreliably: it is an RPC that collects
    replies until a timeout, so on a busy broker a late reply reads as no worker at all.
    Probed repeatedly it returned ok / not ready / ok / not ready on a healthy system,
which is worse than no check. A flapping probe takes instances out of service.

    The heartbeat proves more, and proves it without asking anyone: beat published, the
    broker delivered, and a worker consumed. That whole chain is what has to work for a
    queued job to reach OCS, and a break anywhere in it is the outage this endpoint exists
    to name.

    For the first minute after a deploy no tick has landed yet, so this reports stale and
readiness is false. That is honest because nothing can be submitted yet, and the container
    healthcheck's start period covers it.
    """
    try:
        seen = cache.get(WORKER_HEARTBEAT_KEY)
    except Exception as error:
        return f"unknown: {error.__class__.__name__}"

    if not seen:
        minutes = WORKER_HEARTBEAT_TTL // 60
        return f"no submission run in the last {minutes} minutes — check beat and the submissions worker"
    return OK


def _check_workflow_config():
    try:
        exists = WorkflowConfig.objects.filter(is_active=True).exists()
    except Exception as error:
        return f"unknown: {error.__class__.__name__}"
    return OK if exists else "no active config — upload and activate one"


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
