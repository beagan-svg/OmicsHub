"""Queue ownership, lifecycle, and failure tests."""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.submission_queue.models import QueueEntry

pytestmark = pytest.mark.django_db


class TestQueue:
    def test_lists_pending_entries_and_the_next_one(self, logged_in, queued):
        queued("READY-1")

        response = logged_in.get(reverse("web_ui:queue"))

        assert b"READY-1" in response.content
        assert b"Next eligible submission" in response.content
        assert f"requested by {response.wsgi_request.user}".encode() in response.content
        assert b"Queue status" in response.content

    def test_users_do_not_see_each_others_queues(self, logged_in, queued, client, django_user_model):
        queued("READY-1")
        other = django_user_model.objects.create_user(username="other", email="o@b.org")
        client.force_login(other)

        assert b"READY-1" not in client.get(reverse("web_ui:queue")).content

    def test_cancelling_a_pending_entry(self, logged_in, queued):
        entry = queued("READY-1")

        logged_in.post(reverse("web_ui:cancel", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert entry.status == QueueEntry.Status.CANCELLED

    def test_pausing_hides_the_next_submission_and_persists(self, logged_in, user, queued):
        queued("READY-1")

        logged_in.post(reverse("web_ui:toggle-queue-pause"), follow=True)

        user.refresh_from_db()
        assert user.queue_paused is True
        response = logged_in.get(reverse("web_ui:queue"))
        assert response.context["queue_paused"] is True
        assert b"Next eligible submission" not in response.content

    def test_resuming_restores_the_next_submission(self, logged_in, user, queued):
        queued("READY-1")
        user.queue_paused = True
        user.save(update_fields=["queue_paused"])

        logged_in.post(reverse("web_ui:toggle-queue-pause"), follow=True)

        user.refresh_from_db()
        assert user.queue_paused is False
        assert b"Next eligible submission" in logged_in.get(reverse("web_ui:queue")).content

    def test_deleting_a_pending_entry_removes_it(self, logged_in, queued):
        entry = queued("READY-1")

        logged_in.post(reverse("web_ui:delete-queue-entry", args=[entry.pk]), follow=True)

        assert not QueueEntry.objects.filter(pk=entry.pk).exists()

    def test_deleting_another_users_entry_is_refused(self, logged_in, queued, client, django_user_model):
        entry = queued("READY-1")
        other = django_user_model.objects.create_user(username="other", email="o@b.org")
        client.force_login(other)

        response = client.post(reverse("web_ui:delete-queue-entry", args=[entry.pk]))

        assert response.status_code == 404
        assert QueueEntry.objects.filter(pk=entry.pk).exists()

    def test_deleting_a_submitting_entry_leaves_it_untouched(self, logged_in, queued):
        entry = queued("READY-1")
        entry.status = QueueEntry.Status.SUBMITTING
        entry.save(update_fields=["status"])

        logged_in.post(reverse("web_ui:delete-queue-entry", args=[entry.pk]), follow=True)

        assert QueueEntry.objects.filter(pk=entry.pk).exists()


class TestFailedJobs:
    def test_lists_failures_with_the_error(self, logged_in, queued):
        entry = queued("BAD-1")
        entry.status = QueueEntry.Status.FAILED
        entry.error_message = "OCS rejected the demand"
        entry.save()

        response = logged_in.get(reverse("web_ui:failed"))

        assert b"OCS rejected the demand" in response.content

    def test_separates_running_ocs_failures_from_submission_failures(self, logged_in, queued):
        entry = queued("OCS-FAILED-1")
        entry.status = QueueEntry.Status.FAILED
        entry.demand_id = "demand-1"
        entry.error_message = "Workflow failed in OCS."
        entry.save()

        response = logged_in.get(reverse("web_ui:failed"))

        assert response.context["entries"] == []
        assert response.context["running_failures"] == [entry]
        assert b"Running job failures" in response.content
        assert b"Workflow failed in OCS." in response.content

    def test_failure_badge_combines_submission_and_running_failures(self, logged_in, queued):
        submission_failure = queued("SUBMISSION-FAILED-1")
        submission_failure.status = QueueEntry.Status.FAILED
        submission_failure.save()
        running_failure = queued("RUNNING-FAILED-1")
        running_failure.status = QueueEntry.Status.FAILED
        running_failure.demand_id = "demand-1"
        running_failure.save()

        response = logged_in.get(reverse("web_ui:failed"))

        assert response.context["failure_count"] == 2
        assert b'<span class="visually-hidden">2 </span>2</span>' in response.content

    def test_retry_puts_it_back_on_the_queue(self, logged_in, queued):
        entry = queued("BAD-1")
        entry.status = QueueEntry.Status.FAILED
        entry.demand_id = "old-demand"
        entry.submitted_at = timezone.now()
        entry.error_message = "boom"
        entry.save()

        logged_in.post(reverse("web_ui:retry", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert entry.status == QueueEntry.Status.PENDING
        assert entry.demand_id == ""
        assert entry.submitted_at is None
        assert entry.error_message == ""

    def test_delete_removes_the_entry(self, logged_in, queued):
        entry = queued("BAD-1")
        entry.status = QueueEntry.Status.FAILED
        entry.save()

        logged_in.post(reverse("web_ui:delete-job", args=[entry.pk]), follow=True)

        assert not QueueEntry.objects.filter(pk=entry.pk).exists()

    def test_a_submitted_entry_cannot_be_deleted(self, logged_in, queued):
        entry = queued("RUNNING-1")
        entry.status = QueueEntry.Status.SUBMITTED
        entry.save()

        logged_in.post(reverse("web_ui:delete-job", args=[entry.pk]), follow=True)

        assert QueueEntry.objects.filter(pk=entry.pk).exists()


class TestQueueAndFailures:
    def test_cancelling_a_pending_entry(self, logged_in, queued_entry):
        entry = queued_entry("READY-1")

        response = logged_in.post(reverse("web_ui:cancel", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert b"Cancelled READY-1" in response.content
        assert entry.status == QueueEntry.Status.CANCELLED

    def test_an_entry_already_on_its_way_to_ocs_cannot_be_cancelled(self, logged_in, queued_entry):
        entry = queued_entry("READY-1")
        QueueEntry.objects.filter(pk=entry.pk).update(status=QueueEntry.Status.SUBMITTING)

        response = logged_in.post(reverse("web_ui:cancel", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert b"already being submitted" in response.content
        assert entry.status == QueueEntry.Status.SUBMITTING

    def test_retrying_a_failed_entry_puts_it_back_on_the_queue(self, logged_in, queued_entry):
        entry = queued_entry("READY-1")
        QueueEntry.objects.filter(pk=entry.pk).update(
            status=QueueEntry.Status.FAILED, error_message="ocs exited 1"
        )

        listing = logged_in.get(reverse("web_ui:failed"))
        assert b"ocs exited 1" in listing.content

        response = logged_in.post(reverse("web_ui:retry", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert b"READY-1 is back on the queue" in response.content
        assert entry.status == QueueEntry.Status.PENDING
        assert entry.error_message == ""

    def test_deleting_a_failed_entry(self, logged_in, queued_entry):
        entry = queued_entry("READY-1")
        QueueEntry.objects.filter(pk=entry.pk).update(status=QueueEntry.Status.FAILED)

        response = logged_in.post(reverse("web_ui:delete-job", args=[entry.pk]), follow=True)

        assert b"Deleted the failed entry for READY-1" in response.content
        assert not QueueEntry.objects.filter(pk=entry.pk).exists()

    def test_delete_confirms_first_but_retry_does_not(self, logged_in, queued_entry):
        """Delete is irreversible; Retry is not, so only Delete asks first."""
        entry = queued_entry("READY-1")
        QueueEntry.objects.filter(pk=entry.pk).update(status=QueueEntry.Status.FAILED)

        response = logged_in.get(reverse("web_ui:failed"))
        text = response.content.decode()

        retry_button = text[
            text.index('aria-label="Retry') : text.index("</button>", text.index('aria-label="Retry'))
        ]
        delete_button = text[
            text.index('aria-label="Delete') : text.index("</button>", text.index('aria-label="Delete'))
        ]
        assert "onclick" not in retry_button
        assert "return confirm(" in delete_button

    def test_a_live_entry_cannot_be_deleted(self, logged_in, queued_entry):
        entry = queued_entry("READY-1")

        response = logged_in.post(reverse("web_ui:delete-job", args=[entry.pk]), follow=True)

        assert b"Only failed entries can be deleted" in response.content
        assert QueueEntry.objects.filter(pk=entry.pk).exists()


class TestOtherPeoplesJobs:
    """One user must not be able to see or touch another user's queue entry."""

    @pytest.fixture
    def theirs(self, other_client, active_config, make_sample, other_user):
        make_sample("THEIRS-1")
        other_client.post(reverse("web_ui:submit-confirm"), {"fastq_names": ["THEIRS-1"]})
        entry = QueueEntry.objects.get(sample__fastq_name="THEIRS-1")
        assert entry.requested_by == other_user
        return entry

    def test_it_is_not_on_your_queue_page(self, logged_in, theirs):
        assert logged_in.get(reverse("web_ui:queue")).context["entries"] == []

    def test_it_is_not_on_your_failures_page(self, logged_in, theirs):
        QueueEntry.objects.filter(pk=theirs.pk).update(status=QueueEntry.Status.FAILED)

        response = logged_in.get(reverse("web_ui:failed"))

        assert response.context["entries"] == []
        assert b"THEIRS-1" not in response.content

    def test_you_cannot_cancel_it(self, logged_in, theirs):
        response = logged_in.post(reverse("web_ui:cancel", args=[theirs.pk]))

        theirs.refresh_from_db()
        assert response.status_code == 404
        assert theirs.status == QueueEntry.Status.PENDING

    def test_you_cannot_retry_it(self, logged_in, theirs):
        QueueEntry.objects.filter(pk=theirs.pk).update(status=QueueEntry.Status.FAILED, error_message="x")

        response = logged_in.post(reverse("web_ui:retry", args=[theirs.pk]))

        theirs.refresh_from_db()
        assert response.status_code == 404
        assert theirs.status == QueueEntry.Status.FAILED
        assert theirs.error_message == "x"

    def test_you_cannot_delete_it(self, logged_in, theirs):
        QueueEntry.objects.filter(pk=theirs.pk).update(status=QueueEntry.Status.FAILED)

        response = logged_in.post(reverse("web_ui:delete-job", args=[theirs.pk]))

        assert response.status_code == 404
        assert QueueEntry.objects.filter(pk=theirs.pk).exists()
