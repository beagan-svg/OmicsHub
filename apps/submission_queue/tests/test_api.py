"""The queue API, including the choose-and-confirm flow for an unresolved modality."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.sample_catalog.models import NOT_COMPLETED, Stage
from apps.submission_queue.models import QueueEntry

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client(user):
    api_client = APIClient()
    api_client.force_authenticate(user)
    return api_client


class TestPlan:
    def test_returns_the_command_without_queueing_anything(self, api_client, active_config, make_sample):
        make_sample("READY-1")

        response = api_client.post("/api/queue/plan/", {"fastq_names": ["READY-1"]}, format="json")

        assert response.status_code == 200
        entry = response.json()["entries"][0]
        assert entry["stage"] == Stage.ALIGN
        assert entry["command"].startswith("ocs fastqs align tenx-arc")
        assert not QueueEntry.objects.exists()

    def test_reports_skipped_samples_with_a_reason(self, api_client, active_config, make_sample):
        make_sample("WAITING-1", ingest=NOT_COMPLETED)

        response = api_client.post("/api/queue/plan/", {"fastq_names": ["WAITING-1"]}, format="json")

        assert response.json()["skipped"][0]["reason"] == "ingest_incomplete"

    def test_an_unrecognised_prefix_plans_as_rtx(self, api_client, active_config, make_sample):
        """An unknown batch prefix is classified as RTX."""
        make_sample("ODD-1", batch_name_from_vendor="ZZZ-1", library_prep_method_name="10xV4")

        response = api_client.post("/api/queue/plan/", {"fastq_names": ["ODD-1"]}, format="json")

        body = response.json()
        assert body["modality_required"] == []
        assert body["entries"][0]["modality"] == "RTX"

    def test_unsynced_samples_are_rejected(self, api_client, active_config):
        response = api_client.post("/api/queue/plan/", {"fastq_names": ["MISSING-1"]}, format="json")

        assert response.status_code == 400
        assert "MISSING-1" in str(response.json())

    def test_requires_exactly_one_selector(self, api_client, active_config):
        response = api_client.post(
            "/api/queue/plan/",
            {"fastq_names": ["A"], "batch_name_from_vendor": "MTX-22068"},
            format="json",
        )

        assert response.status_code == 400

    def test_without_an_active_config_it_refuses(self, api_client, make_sample):
        make_sample("READY-1")

        response = api_client.post("/api/queue/plan/", {"fastq_names": ["READY-1"]}, format="json")

        assert response.status_code == 400
        assert "config" in str(response.json()).lower()


class TestConfirm:
    def test_queues_the_planned_entry(self, api_client, active_config, make_sample):
        make_sample("READY-1")

        response = api_client.post("/api/queue/", {"fastq_names": ["READY-1"]}, format="json")

        assert response.status_code == 201
        entry = QueueEntry.objects.get()
        assert entry.sample.fastq_name == "READY-1"
        assert entry.status == QueueEntry.Status.PENDING
        assert entry.modality_source == "inferred"

    def test_refuses_a_modality_the_config_cannot_run(self, api_client, active_config, make_sample):
        """RFX resolves cleanly from the batch name, but this config defines no RFX workflow."""
        make_sample("ODD-1", batch_name_from_vendor="RFX-1")

        response = api_client.post("/api/queue/", {"fastq_names": ["ODD-1"]}, format="json")

        assert response.status_code == 400
        # Refusals travel in the standard error envelope; the samples needing a choice and
        # the modalities on offer are inside it, so the api_client can prompt from one payload.
        error = response.json()["error"]["message"]
        assert error["modality_required"] == ["ODD-1"]
        assert error["available_modalities"] == ["MTX", "RTX"]
        assert not QueueEntry.objects.exists()

    def test_a_confirmed_modality_lets_it_through(self, api_client, active_config, make_sample):
        make_sample("ODD-1", batch_name_from_vendor="ZZZ-1")

        response = api_client.post(
            "/api/queue/", {"fastq_names": ["ODD-1"], "modality": "MTX"}, format="json"
        )

        assert response.status_code == 201
        entry = QueueEntry.objects.get()
        assert entry.modality == "MTX"
        assert entry.modality_source == "user_confirmed"

    def test_an_unknown_modality_is_rejected(self, api_client, active_config, make_sample):
        make_sample("ODD-1", batch_name_from_vendor="ZZZ-1")

        response = api_client.post(
            "/api/queue/", {"fastq_names": ["ODD-1"], "modality": "XYZ"}, format="json"
        )

        assert response.status_code == 400
        assert not QueueEntry.objects.exists()

    def test_confirming_twice_does_not_queue_the_job_twice(self, api_client, active_config, make_sample):
        make_sample("READY-1")
        api_client.post("/api/queue/", {"fastq_names": ["READY-1"]}, format="json")

        response = api_client.post("/api/queue/", {"fastq_names": ["READY-1"]}, format="json")

        assert response.json()["already_queued"] == ["READY-1"]
        assert QueueEntry.objects.count() == 1

    def test_the_notify_email_defaults_to_the_users_own(self, api_client, active_config, make_sample, user):
        make_sample("READY-1")

        api_client.post("/api/queue/", {"fastq_names": ["READY-1"]}, format="json")

        assert QueueEntry.objects.get().notify_email == user.email
        assert user.email in QueueEntry.objects.get().command

    def test_a_whole_batch_can_be_queued(self, api_client, active_config, make_sample):
        make_sample("B-1", batch_name_from_vendor="MTX-22068")
        make_sample("B-2", batch_name_from_vendor="MTX-22068")

        response = api_client.post("/api/queue/", {"batch_name_from_vendor": "MTX-22068"}, format="json")

        assert response.status_code == 201
        assert QueueEntry.objects.count() == 2


class TestListingAndCancelling:
    def test_users_only_see_their_own_entries(
        self, api_client, active_config, make_sample, django_user_model
    ):
        make_sample("MINE-1")
        api_client.post("/api/queue/", {"fastq_names": ["MINE-1"]}, format="json")

        other = django_user_model.objects.create_user(username="other", email="other@example.org")
        other_client = APIClient()
        other_client.force_authenticate(other)

        assert other_client.get("/api/queue/").json()["count"] == 0

    def test_staff_see_every_entry(self, api_client, active_config, make_sample, django_user_model):
        make_sample("MINE-1")
        api_client.post("/api/queue/", {"fastq_names": ["MINE-1"]}, format="json")

        staff = django_user_model.objects.create_user(
            username="admin", email="admin@example.org", is_staff=True
        )
        staff_client = APIClient()
        staff_client.force_authenticate(staff)

        assert staff_client.get("/api/queue/").json()["count"] == 1

    def test_a_pending_entry_can_be_cancelled(self, api_client, active_config, make_sample):
        make_sample("READY-1")
        api_client.post("/api/queue/", {"fastq_names": ["READY-1"]}, format="json")
        entry = QueueEntry.objects.get()

        response = api_client.post(f"/api/queue/{entry.pk}/cancel/")

        entry.refresh_from_db()
        assert response.status_code == 200
        assert entry.status == QueueEntry.Status.CANCELLED

    def test_a_submitted_entry_is_left_alone_rather_than_cancelled(
        self, api_client, active_config, make_sample
    ):
        """It already has a demand at OCS; cancelling here would misrepresent that.

        A no-op, not an error: the worker claiming an entry ahead of a cancel request is an
        ordinary race, not a client mistake, so this matches the web_ui cancel view's own
        forgiving handling of the same race rather than treating it as a 400.
        """
        make_sample("READY-1")
        api_client.post("/api/queue/", {"fastq_names": ["READY-1"]}, format="json")
        entry = QueueEntry.objects.get()
        entry.status = QueueEntry.Status.SUBMITTED
        entry.save()

        response = api_client.post(f"/api/queue/{entry.pk}/cancel/")

        entry.refresh_from_db()
        assert response.status_code == 200
        assert entry.status == QueueEntry.Status.SUBMITTED

    def test_entries_can_be_filtered_by_status(self, api_client, active_config, make_sample):
        make_sample("READY-1")
        api_client.post("/api/queue/", {"fastq_names": ["READY-1"]}, format="json")

        assert api_client.get("/api/queue/?status=PENDING").json()["count"] == 1
        assert api_client.get("/api/queue/?status=SUBMITTED").json()["count"] == 0

    def test_authentication_is_required(self):
        assert APIClient().get("/api/queue/").status_code in (401, 403)
