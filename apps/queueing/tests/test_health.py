"""The readiness endpoint reports each dependency the backend needs."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.queueing import tasks
from apps.queueing.tasks import WORKER_HEARTBEAT_KEY, WORKER_HEARTBEAT_TTL
from apps.workflows.models import WorkflowConfig
from omicshub import health as health_module

pytestmark = pytest.mark.django_db


@pytest.fixture
def broker_up(monkeypatch):
    """Broker answering, and a submission run recorded within the heartbeat window.

    The broker really is running during a test run, so left unpatched these tests would
    pass or fail on whatever the developer's machine happens to be doing.
    """
    monkeypatch.setattr(health_module, "_check_broker", lambda: "ok")
    cache.set(WORKER_HEARTBEAT_KEY, "2026-08-16T00:00:00+00:00", WORKER_HEARTBEAT_TTL)


def test_needs_no_authentication(broker_up):
    """It is what tells you the app is up, so it cannot require a working login.

    Asserted as "not turned away" rather than as a specific code, because either health
    answer is fine here , 401 or 403 is the failure.
    """
    assert APIClient().get("/healthz/").status_code not in (401, 403)


def test_reports_ready_when_everything_is_up(broker_up, config, user):
    WorkflowConfig.objects.create(
        name="config.jsonc", raw="{}", data=config, uploaded_by=user, is_active=True
    )

    response = APIClient().get("/healthz/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_a_missing_config_is_reported_without_failing_readiness(broker_up):
    """Nothing to submit against is a setup step, not an outage , it must not gate rollout."""
    response = APIClient().get("/healthz/")

    assert response.status_code == 200
    assert "no active config" in response.json()["checks"]["workflow_config"]


def test_a_broken_broker_fails_readiness(monkeypatch, config, user):
    monkeypatch.setattr(health_module, "_check_broker", lambda: "unavailable: OperationalError")

    response = APIClient().get("/healthz/")

    assert response.status_code == 503
    assert response.json()["status"] == "not ready"


def test_database_check_reports_ok_when_reachable(broker_up):
    assert health_module._check_database() == "ok"


class TestSubmissionsWorkerCheck:
    """A queue nobody consumes accepts jobs forever and submits none of them.

    Every other signal looks healthy in that state , the broker is up, pages render, entries
    queue , so this is the check that tells the difference. It went missing once, and three
    dead workers reported green for an hour.
    """

    def test_ok_when_the_task_has_run_recently(self):
        cache.set(WORKER_HEARTBEAT_KEY, "2026-08-16T00:00:00+00:00", WORKER_HEARTBEAT_TTL)

        assert health_module._check_submissions_worker() == "ok"

    def test_says_what_to_check_when_no_run_is_recorded(self):
        cache.delete(WORKER_HEARTBEAT_KEY)

        message = health_module._check_submissions_worker()

        assert "no submission run" in message
        assert "beat" in message and "submissions worker" in message

    def test_the_task_records_the_heartbeat_before_it_can_return_early(self, active_config):
        """An empty queue returns early, and that run still proves the chain works."""
        cache.delete(WORKER_HEARTBEAT_KEY)

        tasks.process_next_queue_entry()

        assert cache.get(WORKER_HEARTBEAT_KEY)

    def test_a_cache_that_raises_is_reported_not_propagated(self, monkeypatch):
        def explode(key):
            raise OSError("redis went away")

        monkeypatch.setattr(health_module.cache, "get", explode)

        assert health_module._check_submissions_worker() == "unknown: OSError"

    def test_it_does_not_broadcast_to_the_workers(self, monkeypatch):
        """`inspect()` is an RPC that times out into a false negative , the flapping probe
        this check replaced. Nothing here may reintroduce it."""

        def never_called(*args, **kwargs):
            raise AssertionError("the health check must not poll the workers")

        monkeypatch.setattr(health_module.current_app.control, "inspect", never_called)
        cache.set(WORKER_HEARTBEAT_KEY, "2026-08-16T00:00:00+00:00", WORKER_HEARTBEAT_TTL)

        assert health_module._check_submissions_worker() == "ok"


class TestWorkerCheckGatesReadiness:
    def test_a_dead_submissions_worker_fails_readiness(self, monkeypatch, config, user):
        monkeypatch.setattr(health_module, "_check_broker", lambda: "ok")
        cache.delete(WORKER_HEARTBEAT_KEY)

        response = APIClient().get("/healthz/")

        assert response.status_code == 503
        assert response.json()["status"] == "not ready"
        assert "no submission run" in response.json()["checks"]["submissions_worker"]

    def test_it_is_reported_alongside_the_others(self, broker_up):
        response = APIClient().get("/healthz/")

        assert response.json()["checks"]["submissions_worker"] == "ok"

    def test_a_down_cache_does_not_report_the_worker_as_dead(self, monkeypatch):
        """The heartbeat lives in the cache, so with the cache gone its absence says
        nothing about the worker , and naming the wrong dependency sends whoever is paged
        to the wrong place."""
        monkeypatch.setattr(health_module, "_check_cache", lambda: "unavailable: ConnectionError")

        response = APIClient().get("/healthz/")

        assert response.status_code == 503
        assert response.json()["checks"]["submissions_worker"] == "unknown: cache unavailable"
