"""The queue API driven as a client would drive it, and checked against the web UI.

The API and the pages are meant to be two doors onto one planner. These tests walk the
API's own plan → confirm → list → cancel journey, then plan the same selection through
both doors and insist the answers match — which is the thing that actually breaks when
either side starts deciding something for itself.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import NOT_COMPLETED, Stage
from apps.queueing.models import QueueEntry

pytestmark = pytest.mark.django_db

PLAN = reverse("queueing:queue-plan")
QUEUE = reverse("queueing:queue-list")


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def other_api(db, django_user_model):
    other = django_user_model.objects.create_user(
        username="colleague", email="colleague@alleninstitute.org", password="password"
    )
    client = APIClient()
    client.force_authenticate(other)
    return client, other


class TestSignedOut:
    def test_nothing_is_readable_or_plannable_without_signing_in(self):
        anonymous = APIClient()

        assert anonymous.get(QUEUE).status_code in (401, 403)
        assert anonymous.post(PLAN, {}, format="json").status_code in (401, 403)
        assert anonymous.post(QUEUE, {}, format="json").status_code in (401, 403)


class TestPlanThenConfirm:
    def test_a_plan_can_be_read_then_confirmed_then_listed_then_cancelled(
        self, api, active_config, make_sample, user
    ):
        make_sample("READY-1")

        preview = api.post(PLAN, {"fastq_names": ["READY-1"]}, format="json")
        assert preview.status_code == 200
        assert not QueueEntry.objects.exists()
        planned = preview.json()["entries"][0]

        confirmed = api.post(QUEUE, {"fastq_names": ["READY-1"]}, format="json")
        assert confirmed.status_code == 201
        assert confirmed.json()["created"][0]["command"] == planned["command"]

        entry_id = confirmed.json()["created"][0]["id"]
        listing = api.get(QUEUE).json()
        assert [row["id"] for row in listing["results"]] == [entry_id]
        assert listing["results"][0]["requested_by"] == user.get_username()

        cancelled = api.post(reverse("queueing:queue-cancel", args=[entry_id]))
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == QueueEntry.Status.CANCELLED

    def test_a_plan_says_which_samples_are_carried_by_their_partner(
        self, api, active_config, make_sample
    ):
        make_sample(
            "GEX-1",
            batch_name_from_vendor="MTX-500",
            load_name="LOAD_PAIR",
            library_prep_method_name="10xMultX_GEX",
        )
        make_sample(
            "ATAC-1",
            batch_name_from_vendor="ATX-500",
            load_name="LOAD_PAIR",
            library_prep_method_name="10xMultX_ATAC",
        )

        body = api.post(PLAN, {"fastq_names": ["GEX-1"]}, format="json").json()

        # The caller asked about one sample and is told about two, so nothing is unaccounted for.
        assert [entry["fastq_name"] for entry in body["entries"]] == ["GEX-1"]
        assert body["covered_by_pair"] == ["ATAC-1"]

    def test_forcing_a_stage_is_recorded_on_the_entry(self, api, active_config, make_sample):
        make_sample("DONE-1", align="COMPLETED", postalign="COMPLETED")

        assert api.post(PLAN, {"fastq_names": ["DONE-1"]}, format="json").json()["entries"] == []

        response = api.post(
            QUEUE, {"fastq_names": ["DONE-1"], "force": Stage.ALIGN.value}, format="json"
        )

        assert response.status_code == 201
        entry = QueueEntry.objects.get()
        assert entry.stage == Stage.ALIGN
        assert entry.forced is True

    def test_batch_processing_reaches_the_stored_command(self, api, active_config, make_sample):
        make_sample(
            "RTX-1",
            batch_name_from_vendor="RTX-900",
            organism_common_name="human",
            library_prep_method_name="10xV4",
            load_name="LOAD_RTX",
        )

        api.post(QUEUE, {"fastq_names": ["RTX-1"], "batch_processing": True}, format="json")

        entry = QueueEntry.objects.get()
        assert entry.batch_processing is True
        assert "--fastq-names RTX-1" in entry.command

    def test_a_selection_of_nothing_but_skips_creates_nothing_and_explains(
        self, api, active_config, make_sample
    ):
        make_sample("WAITING-1", ingest=NOT_COMPLETED)

        response = api.post(QUEUE, {"fastq_names": ["WAITING-1"]}, format="json")

        assert response.status_code == 201
        assert response.json()["created"] == []
        assert response.json()["skipped"][0]["reason"] == "ingest_incomplete"
        assert not QueueEntry.objects.exists()

    def test_an_account_with_no_email_is_asked_for_one(
        self, active_config, make_sample, django_user_model
    ):
        nameless = django_user_model.objects.create_user(username="nomail", password="password")
        client = APIClient()
        client.force_authenticate(nameless)
        make_sample("READY-1")

        response = client.post(QUEUE, {"fastq_names": ["READY-1"]}, format="json")

        assert response.status_code == 400
        assert "notify_email" in str(response.json())
        assert not QueueEntry.objects.exists()

    def test_a_supplied_address_must_be_an_address(self, api, active_config, make_sample):
        make_sample("READY-1")

        response = api.post(
            QUEUE, {"fastq_names": ["READY-1"], "notify_email": "not-an-address"}, format="json"
        )

        assert response.status_code == 400
        assert not QueueEntry.objects.exists()

    def test_more_names_than_one_request_may_plan_are_refused(self, api, active_config):
        response = api.post(PLAN, {"fastq_names": [f"S-{n}" for n in range(501)]}, format="json")

        assert response.status_code == 400
        assert "no more than 500" in str(response.json())

    def test_a_batch_nobody_has_synced_is_named_in_the_refusal(self, api, active_config):
        response = api.post(PLAN, {"batch_name_from_vendor": "MTX-99999"}, format="json")

        assert response.status_code == 400
        assert "MTX-99999" in str(response.json())


class TestOtherPeoplesEntries:
    @pytest.fixture
    def theirs(self, other_api, active_config, make_sample):
        client, owner = other_api
        make_sample("THEIRS-1")
        client.post(QUEUE, {"fastq_names": ["THEIRS-1"]}, format="json")
        entry = QueueEntry.objects.get()
        assert entry.requested_by == owner
        return entry

    def test_you_cannot_read_it(self, api, theirs):
        assert api.get(reverse("queueing:queue-detail", args=[theirs.pk])).status_code == 404

    def test_you_cannot_cancel_it(self, api, theirs):
        response = api.post(reverse("queueing:queue-cancel", args=[theirs.pk]))

        theirs.refresh_from_db()
        assert response.status_code == 404
        assert theirs.status == QueueEntry.Status.PENDING

    def test_it_is_not_in_your_listing_even_filtered_by_status(self, api, theirs):
        assert api.get(QUEUE).json()["count"] == 0
        assert api.get(QUEUE, {"status": "PENDING"}).json()["count"] == 0


class TestEntriesAreReadOnly:
    def test_an_entry_cannot_be_edited_or_deleted_through_the_api(
        self, api, active_config, make_sample
    ):
        make_sample("READY-1")
        api.post(QUEUE, {"fastq_names": ["READY-1"]}, format="json")
        entry = QueueEntry.objects.get()
        detail = reverse("queueing:queue-detail", args=[entry.pk])

        assert api.patch(detail, {"command": "rm -rf /"}, format="json").status_code == 405
        assert api.put(detail, {"command": "rm -rf /"}, format="json").status_code == 405
        assert api.delete(detail).status_code == 405
        entry.refresh_from_db()
        assert entry.command.startswith("ocs fastqs align")

    def test_a_stranded_entry_cannot_be_cancelled_away(self, api, active_config, make_sample):
        make_sample("READY-1")
        api.post(QUEUE, {"fastq_names": ["READY-1"]}, format="json")
        entry = QueueEntry.objects.get()
        QueueEntry.objects.filter(pk=entry.pk).update(status=QueueEntry.Status.STRANDED)

        response = api.post(reverse("queueing:queue-cancel", args=[entry.pk]))

        entry.refresh_from_db()
        assert response.status_code == 400
        assert entry.status == QueueEntry.Status.STRANDED


class TestTheTwoDoorsAgree:
    """The API preview and the web review modal must plan the same selection the same way."""

    def test_the_command_is_identical_through_the_api_and_the_page(
        self, api, logged_in, active_config, make_sample
    ):
        make_sample("READY-1")

        from_api = api.post(PLAN, {"fastq_names": ["READY-1"]}, format="json").json()["entries"][0]
        page = logged_in.post(reverse("web:submit-review"), {"fastq_names": ["READY-1"]})
        from_page = page.context["plan"].entries[0]

        assert from_api["command"] == from_page.command
        assert from_api["stage"] == from_page.stage
        assert from_api["spacing"] == from_page.spacing

    def test_a_skip_reason_is_identical_through_both(
        self, api, logged_in, active_config, make_sample
    ):
        make_sample("WAITING-1", ingest=NOT_COMPLETED)

        from_api = api.post(PLAN, {"fastq_names": ["WAITING-1"]}, format="json").json()["skipped"][0]
        page = logged_in.post(reverse("web:submit-review"), {"fastq_names": ["WAITING-1"]})
        from_page = page.context["plan"].skipped[0]

        assert (from_api["reason"], from_api["detail"]) == (from_page.reason, from_page.detail)

    def test_a_job_queued_through_the_api_shows_on_the_web_queue(
        self, api, logged_in, active_config, make_sample
    ):
        make_sample("READY-1")

        api.post(QUEUE, {"fastq_names": ["READY-1"]}, format="json")

        entries = logged_in.get(reverse("web:queue")).context["entries"]
        assert [entry.sample.fastq_name for entry in entries] == ["READY-1"]

    def test_a_job_queued_on_the_page_is_cancellable_through_the_api(
        self, api, logged_in, active_config, make_sample
    ):
        make_sample("READY-1")
        logged_in.post(reverse("web:submit-confirm"), {"fastq_names": ["READY-1"]})
        entry = QueueEntry.objects.get()

        response = api.post(reverse("queueing:queue-cancel", args=[entry.pk]))

        entry.refresh_from_db()
        assert response.status_code == 200
        assert entry.status == QueueEntry.Status.CANCELLED

    def test_neither_door_queues_the_same_stage_twice(
        self, api, logged_in, active_config, make_sample
    ):
        make_sample("READY-1")
        logged_in.post(reverse("web:submit-confirm"), {"fastq_names": ["READY-1"]})

        response = api.post(QUEUE, {"fastq_names": ["READY-1"]}, format="json")

        assert response.json()["already_queued"] == ["READY-1"]
        assert QueueEntry.objects.count() == 1
