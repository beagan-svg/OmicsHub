"""The Job Monitor / Failures pages' AWS-credential-gated log viewer.

AWS itself is never touched here: apps.ocs_integration.log_credentials is monkeypatched
at its own boundary (log_credentials has its own Stubber-based tests). This file is
about the view layer -- authorization, session isolation, and that secrets never round-
trip through a response.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.ocs_integration import dynamodb, log_credentials, s3
from apps.sample_catalog.models import Stage
from apps.submission_queue.models import QueueEntry

from .conftest import stub_valid_sts

pytestmark = pytest.mark.django_db

FAKE_ACCESS_KEY = "test-access-key"
FAKE_SECRET_KEY = "fake-secret-not-a-real-value-000000000000"
FAKE_SESSION_TOKEN = "fake-session-token-not-a-real-value"


def submit(client, **overrides):
    payload = {
        "access_key": FAKE_ACCESS_KEY,
        "secret_key": FAKE_SECRET_KEY,
        "session_token": FAKE_SESSION_TOKEN,
    }
    payload.update(overrides)
    return client.post(reverse("web_ui:job-credentials-submit"), payload)


class TestCredentialsSubmit:
    def test_valid_credentials_return_identity_never_the_secrets(self, logged_in, monkeypatch):
        monkeypatch.setattr(
            log_credentials,
            "validate_credentials",
            lambda request, a, s, t: log_credentials.ValidatedIdentity(
                account="123456789012", arn="arn:aws:sts::123456789012:assumed-role/x/y"
            ),
        )

        response = submit(logged_in)

        assert response.status_code == 200
        body = response.json()
        assert body == {
            "status": "valid",
            "account": "123456789012",
            "arn": "arn:aws:sts::123456789012:assumed-role/x/y",
        }
        assert FAKE_SECRET_KEY not in response.content.decode()
        assert FAKE_SESSION_TOKEN not in response.content.decode()

    def test_invalid_credentials_return_a_redacted_message(self, logged_in, monkeypatch):
        def raise_invalid(request, a, s, t):
            raise log_credentials.CredentialError("InvalidClientTokenId", "AWS rejected these credentials.")

        monkeypatch.setattr(log_credentials, "validate_credentials", raise_invalid)

        response = submit(logged_in)

        assert response.status_code == 400
        assert response.json() == {
            "status": "invalid",
            "code": "InvalidClientTokenId",
            "message": "AWS rejected these credentials.",
        }

    def test_expired_credentials_return_a_redacted_message(self, logged_in, monkeypatch):
        def raise_expired(request, a, s, t):
            raise log_credentials.CredentialError("ExpiredToken", "These credentials have expired.")

        monkeypatch.setattr(log_credentials, "validate_credentials", raise_expired)

        response = submit(logged_in)

        assert response.status_code == 400
        assert response.json()["code"] == "ExpiredToken"

    @pytest.mark.parametrize("missing", ["access_key", "secret_key", "session_token"])
    def test_missing_a_value_is_rejected(self, logged_in, missing):
        # The real validate_credentials, not monkeypatched: it enforces this itself (unit
        # tested directly in apps/ocs_integration/tests/test_log_credentials.py). This
        # confirms the view passes an empty string through rather than substituting a
        # default, and surfaces the resulting error correctly.
        response = submit(logged_in, **{missing: ""})

        assert response.status_code == 400
        assert response.json()["code"] == "MissingValue"

    def test_credentials_never_appear_in_the_request_url(self, logged_in):
        """The functional requirement is "never in a URL, never in browser history" --
        this locks in that submission is a POST body, not a query string, at the URL
        resolution level."""
        url = reverse("web_ui:job-credentials-submit")
        assert "?" not in url
        assert FAKE_ACCESS_KEY not in url

    def test_requires_login(self, client):
        response = submit(client)
        assert response.status_code == 302
        assert "/accounts/login/" in response["Location"]


class TestCredentialsStatusAndClear:
    def test_status_reports_required_with_no_cached_credentials(self, logged_in):
        response = logged_in.get(reverse("web_ui:job-credentials-status"))
        assert response.json() == {"status": "required"}

    def test_status_reports_valid_after_a_successful_submit(self, logged_in, monkeypatch):
        stub_valid_sts(monkeypatch)
        submit(logged_in)

        response = logged_in.get(reverse("web_ui:job-credentials-status"))

        assert response.json()["status"] == "valid"

    def test_clear_removes_the_cached_credentials(self, logged_in, monkeypatch):
        stub_valid_sts(monkeypatch)
        submit(logged_in)
        assert logged_in.get(reverse("web_ui:job-credentials-status")).json()["status"] == "valid"

        response = logged_in.post(reverse("web_ui:job-credentials-clear"))

        assert response.json() == {"status": "cleared"}
        assert logged_in.get(reverse("web_ui:job-credentials-status")).json()["status"] == "required"


class TestLogAuthorizationBoundary:
    def _logs_url(self, demand_id):
        return reverse("web_ui:job-demand-logs", args=[demand_id])

    def test_no_cached_credentials_returns_401(self, logged_in, make_sample):
        sample = make_sample("RUN-1", align="IN_PROGRESS")
        demand_id = sample.stage_statuses.get(stage=Stage.ALIGN).demand_id

        response = logged_in.get(self._logs_url(demand_id), {"stage": Stage.ALIGN.value})

        assert response.status_code == 401
        assert response.json()["status"] == "no_credentials"

    def _with_valid_credentials(self, client, monkeypatch):
        stub_valid_sts(monkeypatch)
        submit(client)

    def test_running_demand_is_visible(self, logged_in, make_sample, monkeypatch):
        sample = make_sample("RUN-2", align="IN_PROGRESS")
        demand_id = sample.stage_statuses.get(stage=Stage.ALIGN).demand_id
        self._with_valid_credentials(logged_in, monkeypatch)
        monkeypatch.setattr(log_credentials, "fetch_job_logs", lambda request, d, execution_arn, **kwargs: [])

        response = logged_in.get(self._logs_url(demand_id), {"stage": Stage.ALIGN.value})

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "events": []}

    def test_recently_finished_demand_is_visible(self, logged_in, make_sample, monkeypatch):
        sample = make_sample("RUN-3", align="COMPLETED")
        demand_id = sample.stage_statuses.get(stage=Stage.ALIGN).demand_id
        self._with_valid_credentials(logged_in, monkeypatch)
        monkeypatch.setattr(log_credentials, "fetch_job_logs", lambda request, d, execution_arn, **kwargs: [])

        response = logged_in.get(self._logs_url(demand_id), {"stage": Stage.ALIGN.value})

        assert response.status_code == 200

    def test_failed_queue_entry_belonging_to_the_reader_is_visible(
        self, logged_in, user, make_sample, monkeypatch
    ):
        sample = make_sample("RUN-4")
        QueueEntry.objects.create(
            sample=sample,
            stage=Stage.ALIGN,
            requested_by=user,
            modality="RNASeq",
            modality_source=QueueEntry.ModalitySource.INFERRED,
            command_args=["ocs"],
            command="ocs",
            spacing=180,
            status=QueueEntry.Status.FAILED,
            demand_id="demand-ingest",
        )
        self._with_valid_credentials(logged_in, monkeypatch)
        monkeypatch.setattr(log_credentials, "fetch_job_logs", lambda request, d, execution_arn, **kwargs: [])

        response = logged_in.get(self._logs_url("demand-ingest"), {"stage": Stage.ALIGN.value})

        assert response.status_code == 200

    def test_failed_queue_entry_belonging_to_another_user_is_not_visible(
        self, logged_in, make_sample, monkeypatch, django_user_model
    ):
        """The Failure tab is per-reader (via _owned), not global like the Monitor
        page -- a non-staff reader must not unlock another reader's failed submission
        just because they know its demand id."""
        other = django_user_model.objects.create_user(username="someone-else")
        sample = make_sample("RUN-5")
        QueueEntry.objects.create(
            sample=sample,
            stage=Stage.ALIGN,
            requested_by=other,
            modality="RNASeq",
            modality_source=QueueEntry.ModalitySource.INFERRED,
            command_args=["ocs"],
            command="ocs",
            spacing=180,
            status=QueueEntry.Status.FAILED,
            demand_id="demand-theirs-failed",
        )
        self._with_valid_credentials(logged_in, monkeypatch)

        response = logged_in.get(self._logs_url("demand-theirs-failed"), {"stage": Stage.ALIGN.value})

        assert response.status_code == 403
        assert response.json()["status"] == "not_visible"

    def test_unknown_demand_id_is_not_visible(self, logged_in, monkeypatch):
        self._with_valid_credentials(logged_in, monkeypatch)

        response = logged_in.get(self._logs_url("no-such-demand"), {"stage": Stage.ALIGN.value})

        assert response.status_code == 403
        assert response.json()["status"] == "not_visible"

    def test_aws_rejection_during_fetch_is_reported_and_deauthorizes(
        self, logged_in, make_sample, monkeypatch
    ):
        sample = make_sample("RUN-6", align="IN_PROGRESS")
        demand_id = sample.stage_statuses.get(stage=Stage.ALIGN).demand_id
        self._with_valid_credentials(logged_in, monkeypatch)

        def raise_expired(request, d, execution_arn, **kwargs):
            raise log_credentials.CredentialError(
                "ExpiredToken", "These credentials have expired.", rejected=True
            )

        monkeypatch.setattr(log_credentials, "fetch_job_logs", raise_expired)

        response = logged_in.get(self._logs_url(demand_id), {"stage": Stage.ALIGN.value})

        assert response.status_code == 401
        assert response.json()["code"] == "ExpiredToken"

    def test_requires_login(self, client):
        response = client.get(self._logs_url("whatever"), {"stage": Stage.ALIGN.value})
        assert response.status_code == 302


class TestSessionIsolation:
    def test_one_users_credentials_are_not_visible_from_another_login(
        self, client, django_user_model, monkeypatch
    ):
        alice = django_user_model.objects.create_user(username="alice", password="password")
        bob = django_user_model.objects.create_user(username="bob", password="password")

        stub_valid_sts(monkeypatch)
        client.force_login(alice)
        submit(client)
        assert client.get(reverse("web_ui:job-credentials-status")).json()["status"] == "valid"

        client.logout()
        client.force_login(bob)

        response = client.get(reverse("web_ui:job-credentials-status"))
        assert response.json()["status"] == "required"


class TestNoFallbackToAppIdentity:
    def test_missing_credentials_never_touch_the_apps_own_aws_clients(
        self, logged_in, make_sample, monkeypatch
    ):
        sample = make_sample("RUN-7", align="IN_PROGRESS")
        demand_id = sample.stage_statuses.get(stage=Stage.ALIGN).demand_id
        dynamodb_calls = []
        s3_calls = []
        monkeypatch.setattr(dynamodb, "get_demands", lambda ids: dynamodb_calls.append(ids) or {})
        monkeypatch.setattr(s3, "_client", lambda: s3_calls.append(1))

        response = logged_in.get(
            reverse("web_ui:job-demand-logs", args=[demand_id]), {"stage": Stage.ALIGN.value}
        )

        assert response.status_code == 401
        assert dynamodb_calls == []
        assert s3_calls == []
