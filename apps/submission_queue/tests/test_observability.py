"""Test correlation IDs, log redaction, and error monitoring instrumentation.

These tests detect missing correlation IDs and redaction failures before deployment.
"""

from __future__ import annotations

import logging
import subprocess

import pytest
import sentry_sdk
from django.core.cache import cache
from rest_framework.test import APIClient

from omicshub import health as health_module
from omicshub.logging_filters import (
    NO_REQUEST_ID,
    REQUEST_ID_HEADER,
    EmailRedactingFilter,
    RequestIDFilter,
    get_request_id,
    reset_request_id,
    scrub_event,
    set_request_id,
)

EMAIL = "bicore@alleninstitute.org"


@pytest.fixture(autouse=True)
def _no_request_id():
    """Start every test with no id in scope.

    The middleware leaves the id set after the response on purpose, and the contextvar is
    process-wide, so without this a test would see whichever id the previous one used.
    """
    token = set_request_id("")
    yield
    reset_request_id(token)


def make_record(message: str, *args, exc_info=None) -> logging.LogRecord:
    return logging.LogRecord(
        name="apps.ocs_integration.cli",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=args,
        exc_info=exc_info,
    )


class TestRequestID:
    """A user reports "it failed at 2pm". The id is what turns that into one log query."""

    def test_a_request_gets_an_id_and_gets_it_back(self, logged_in):
        response = logged_in.get("/healthz/")

        assert response[REQUEST_ID_HEADER]

    def test_an_inbound_id_is_reused_so_the_trail_is_unbroken(self, client):
        response = client.get("/healthz/", headers={"x-request-id": "abc-123"})

        assert response[REQUEST_ID_HEADER] == "abc-123"

    def test_a_junk_inbound_id_is_replaced_rather_than_logged(self, client):
        """The header is client input and lands in every log line , a newline in it would
        forge log entries, and an unbounded one would flood them."""
        forged = "x\nWARNING nothing to see here"

        response = client.get("/healthz/", headers={"x-request-id": forged})

        assert response[REQUEST_ID_HEADER] != forged
        assert "\n" not in response[REQUEST_ID_HEADER]

    def test_an_overlong_inbound_id_is_replaced(self, client):
        response = client.get("/healthz/", headers={"x-request-id": "a" * 500})

        assert len(response[REQUEST_ID_HEADER]) < 100

    def test_the_id_reaches_the_log_records_the_request_produces(self, client, caplog):
        """The whole point: the id on the response is the id in the logs.

        The filter is added to caplog's own handler because that is how it runs in
        production too , on the handler, as the record is emitted, inside the request.
        """
        caplog.handler.addFilter(RequestIDFilter())

        # An unready health check logs `django.request: Service Unavailable`, which is a
        # real record emitted from inside the request rather than one this test fabricates.
        with caplog.at_level(logging.INFO):
            response = client.get("/healthz/", headers={"x-request-id": "trace-me"})

        assert response[REQUEST_ID_HEADER] == "trace-me"
        assert caplog.records
        assert all(record.request_id == "trace-me" for record in caplog.records)

    def test_the_next_request_takes_over_the_id(self, client):
        """The middleware runs first, so no request can inherit the previous one's id.

        The id is deliberately left set after the response , see the middleware , so this
        is what stops one request being logged under another's.
        """
        client.get("/healthz/", headers={"x-request-id": "first"})
        client.get("/healthz/", headers={"x-request-id": "second"})

        assert get_request_id() == "second"

    def test_the_response_log_line_is_correlated_too(self, client, caplog):
        """`django.request` logs the 5xx after the middleware chain returns; that line is
        the one an operator greps for, so it must carry the id rather than a dash."""
        caplog.handler.addFilter(RequestIDFilter())

        with caplog.at_level(logging.INFO):
            client.get("/healthz/", headers={"x-request-id": "after-the-chain"})

        response_logs = [record for record in caplog.records if record.name == "django.request"]
        assert response_logs
        assert all(record.request_id == "after-the-chain" for record in response_logs)

    def test_a_record_with_no_request_in_scope_still_renders(self):
        """Management commands and startup log too, and the format string is not optional."""
        record = make_record("started")

        RequestIDFilter().filter(record)

        assert record.request_id == NO_REQUEST_ID

    def test_the_configured_format_actually_uses_the_filtered_attribute(self, settings):
        """Guards the pairing: dropping the filter would make every log call raise."""
        assert "{request_id}" in settings.LOGGING["formatters"]["verbose"]["format"]
        assert "request_id" in settings.LOGGING["handlers"]["console"]["filters"]


class TestCeleryCorrelation:
    def test_a_published_task_carries_the_publishing_request_id(self):
        from omicshub.logging_filters import _attach_request_id

        token = set_request_id("from-the-web")
        headers: dict = {}
        try:
            _attach_request_id(headers=headers)
        finally:
            reset_request_id(token)

        assert headers["request_id"] == "from-the-web"

    def test_a_running_task_adopts_it(self):
        from omicshub.logging_filters import _adopt_request_id, _clear_request_id

        class Task:
            request = type("Request", (), {"request_id": "from-the-web"})()

        _adopt_request_id(task=Task(), task_id="task-1")
        try:
            assert get_request_id() == "from-the-web"
        finally:
            _clear_request_id()

    def test_beat_work_falls_back_to_the_task_id(self):
        """The sweeps are queued by no request at all, and still need to be correlated."""
        from omicshub.logging_filters import _adopt_request_id, _clear_request_id

        _adopt_request_id(task=object(), task_id="task-1")
        try:
            assert get_request_id() == "task-1"
        finally:
            _clear_request_id()


class TestEmailRedaction:
    """`ocs` submission commands carry `--notify <address>` and that argv gets logged."""

    def test_an_address_in_the_message_is_removed(self):
        record = make_record("Submitting to OCS: %s", f"ocs fastqs align --notify {EMAIL}")

        EmailRedactingFilter().filter(record)

        assert EMAIL not in record.getMessage()
        assert "<redacted-email>" in record.getMessage()

    def test_the_rest_of_the_command_survives(self):
        """Redaction that ate the command would make the log useless instead of unsafe."""
        record = make_record("Submitting to OCS: %s", f"ocs fastqs align --notify {EMAIL} --load-names L1")

        EmailRedactingFilter().filter(record)

        assert "ocs fastqs align --notify" in record.getMessage()
        assert "--load-names L1" in record.getMessage()

    def test_an_address_inside_a_traceback_is_removed(self):
        """`logger.exception` on a failed submission renders CalledProcessError, whose text
        contains the whole argv , the address is in the traceback, not in the message."""
        try:
            raise subprocess.CalledProcessError(1, ["ocs", "align", "--notify", EMAIL])
        except subprocess.CalledProcessError:
            import sys

            record = make_record("Submission outcome unknown", exc_info=sys.exc_info())

        EmailRedactingFilter().filter(record)

        assert EMAIL not in record.exc_text
        assert "<redacted-email>" in record.exc_text

    def test_a_record_without_an_address_keeps_its_lazy_arguments(self):
        """The common case must not pay for the rare one by being rendered early."""
        record = make_record("Synced metadata for %d samples", 42)

        EmailRedactingFilter().filter(record)

        assert record.args == (42,)
        assert record.getMessage() == "Synced metadata for 42 samples"

    def test_the_handler_is_wired_to_use_it(self, settings):
        assert "redact_emails" in settings.LOGGING["handlers"]["console"]["filters"]

    def test_sentry_events_are_scrubbed_too(self):
        """`send_default_pii=False` covers the user record, not an address inside a frame."""
        event = {
            "exception": {"values": [{"value": f"ocs align --notify {EMAIL}"}]},
            "breadcrumbs": [{"message": f"notify {EMAIL}"}],
        }

        scrubbed = scrub_event(event)

        assert EMAIL not in str(scrubbed)
        assert "ocs align --notify" in scrubbed["exception"]["values"][0]["value"]


class TestSentryStaysOffWithoutADSN:
    """Local runs and CI must behave exactly as they did before Sentry was added."""

    def test_no_dsn_is_configured_under_test_settings(self, settings):
        assert settings.SENTRY_DSN == ""

    def test_the_sdk_is_not_active(self):
        """An initialised client would ship every test failure somewhere."""
        assert not sentry_sdk.get_client().is_active()


class TestCacheHealth:
    """The capacity and spacing holds live in the cache; without it the worker mispaces."""

    def test_ok_when_the_cache_round_trips(self):
        assert health_module._check_cache() == "ok"

    def test_a_cache_that_raises_is_reported_not_propagated(self, monkeypatch):
        def explode(*args, **kwargs):
            raise ConnectionError("redis is gone")

        monkeypatch.setattr(cache, "set", explode)

        assert health_module._check_cache() == "unavailable: ConnectionError"

    def test_a_cache_that_accepts_writes_and_keeps_nothing_is_caught(self, monkeypatch):
        """A Redis at maxmemory, or failed over to a read-only replica, answers a ping."""
        monkeypatch.setattr(cache, "get", lambda *args, **kwargs: None)

        assert "did not survive" in health_module._check_cache()

    @pytest.mark.django_db
    def test_a_broken_cache_fails_readiness(self, monkeypatch):
        monkeypatch.setattr(health_module, "_check_broker", lambda: "ok")
        monkeypatch.setattr(health_module, "_check_submissions_worker", lambda: "ok")
        monkeypatch.setattr(health_module, "_check_cache", lambda: "unavailable: ConnectionError")

        response = APIClient().get("/healthz/")

        assert response.status_code == 503
        assert response.json()["status"] == "not ready"
        assert response.json()["checks"]["cache"] == "unavailable: ConnectionError"

    @pytest.mark.django_db
    def test_it_is_reported_alongside_the_others(self, monkeypatch):
        monkeypatch.setattr(health_module, "_check_broker", lambda: "ok")
        monkeypatch.setattr(health_module, "_check_submissions_worker", lambda: "ok")

        assert APIClient().get("/healthz/").json()["checks"]["cache"] == "ok"
