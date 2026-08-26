"""The submission worker: capacity, pacing, and what happens when a submission fails."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.ocs_integration.cli import OCSSubmissionError
from apps.sample_catalog.models import Stage, StageStatus
from apps.submission_queue import tasks
from apps.submission_queue.models import QueueEntry

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_capacity_hold():
    """The hold outlives a test otherwise , it is in the cache, not the database."""
    cache.delete(tasks.CAPACITY_HOLD_KEY)
    yield
    cache.delete(tasks.CAPACITY_HOLD_KEY)


@pytest.fixture
def pending_entry(user, make_sample):
    return QueueEntry.objects.create(
        sample=make_sample("READY-1"),
        stage=Stage.ALIGN,
        requested_by=user,
        modality="MTX",
        modality_source=QueueEntry.ModalitySource.INFERRED,
        notify_email="bicore@alleninstitute.org",
        command_args=["ocs", "fastqs", "align", "tenx-arc"],
        command="ocs fastqs align tenx-arc",
        spacing=180,
    )


@pytest.fixture
def ocs(monkeypatch):
    """Stand in for OCS: records submissions, reports a configurable in-progress count."""

    class FakeOCS:
        def __init__(self):
            self.in_progress = 0
            self.submitted = []
            self.scheduled = []
            self.count_calls = 0

        def count_in_progress(self, demand_type):
            self.count_calls += 1
            return self.in_progress

        def submit(self, command_args):
            self.submitted.append(command_args)
            return "demand-123"

    fake = FakeOCS()
    monkeypatch.setattr(tasks.dynamodb, "count_in_progress", fake.count_in_progress)
    monkeypatch.setattr(tasks.cli, "submit", fake.submit)
    monkeypatch.setattr(
        tasks.process_next_queue_entry,
        "apply_async",
        lambda **kwargs: fake.scheduled.append(kwargs),
    )
    monkeypatch.setattr(
        tasks.process_next_queue_entry, "delay", lambda: fake.scheduled.append({"countdown": 0})
    )
    return fake


def test_submits_the_pending_entry(active_config, pending_entry, ocs):
    tasks.process_next_queue_entry()

    pending_entry.refresh_from_db()
    assert ocs.submitted == [["ocs", "fastqs", "align", "tenx-arc"]]
    assert pending_entry.status == QueueEntry.Status.SUBMITTED
    assert pending_entry.demand_id == "demand-123"
    assert pending_entry.submitted_at is not None


def test_records_the_demand_against_the_sample(active_config, pending_entry, ocs):
    tasks.process_next_queue_entry()

    stage_status = StageStatus.objects.get(sample=pending_entry.sample, stage=Stage.ALIGN)
    assert stage_status.demand_id == "demand-123"
    assert stage_status.status == "SUBMITTED"


def test_waits_for_the_configured_spacing_before_the_next_submission(active_config, pending_entry, ocs):
    tasks.process_next_queue_entry()

    assert ocs.scheduled == [{"countdown": 180}]


def test_at_the_job_limit_nothing_is_submitted_and_the_job_is_not_dropped(active_config, pending_entry, ocs):
    """Jobs wait for capacity , the old behaviour of skipping them lost work."""
    ocs.in_progress = 50  # 50 align + 50 post-align == the configured limit of 100

    tasks.process_next_queue_entry()

    pending_entry.refresh_from_db()
    assert ocs.submitted == []
    assert pending_entry.status == QueueEntry.Status.PENDING


def test_the_limit_queues_no_retry_of_its_own(active_config, pending_entry, ocs):
    """Celery Beat is the only retry mechanism for a full OCS queue.

    Scheduling retries from the task would create one delayed task per Beat interval and
    could submit the backlog without the configured spacing.
    """
    ocs.in_progress = 50

    tasks.process_next_queue_entry()

    assert ocs.scheduled == []


def test_the_limit_holds_off_further_ocs_queries_for_the_poll_interval(active_config, pending_entry, ocs):
    """`poll_interval_hours` has to survive beat calling this again a minute later."""
    ocs.in_progress = 50

    tasks.process_next_queue_entry()
    calls_after_first = ocs.count_calls

    tasks.process_next_queue_entry()

    assert ocs.count_calls == calls_after_first, "second run re-counted OCS during the hold"
    assert cache.get(tasks.CAPACITY_HOLD_KEY)


def test_the_queue_resumes_once_the_hold_expires(active_config, pending_entry, ocs):
    ocs.in_progress = 50
    tasks.process_next_queue_entry()

    # What the TTL does an hour later, without waiting an hour for it.
    cache.delete(tasks.CAPACITY_HOLD_KEY)
    ocs.in_progress = 0

    tasks.process_next_queue_entry()

    assert len(ocs.submitted) == 1
    assert ocs.scheduled == [{"countdown": 180}], "the resumed submission must still be spaced"


def test_below_the_job_limit_it_submits(active_config, pending_entry, ocs):
    ocs.in_progress = 49  # 98 total, one below the limit

    tasks.process_next_queue_entry()

    assert len(ocs.submitted) == 1


def test_a_failed_submission_is_recorded_and_does_not_stall_the_queue(
    active_config, pending_entry, ocs, monkeypatch
):
    pending_entry.demand_id = "old-demand"
    pending_entry.submitted_at = timezone.now()
    pending_entry.save(update_fields=["demand_id", "submitted_at"])

    def fail(command_args):
        raise OCSSubmissionError("OCS rejected the demand")

    monkeypatch.setattr(tasks.cli, "submit", fail)

    tasks.process_next_queue_entry()

    pending_entry.refresh_from_db()
    assert pending_entry.status == QueueEntry.Status.FAILED
    assert pending_entry.demand_id == ""
    assert pending_entry.submitted_at is None
    assert "rejected" in pending_entry.error_message
    assert ocs.scheduled == [{"countdown": 0}]


def test_an_empty_queue_does_not_call_ocs(active_config, ocs):
    tasks.process_next_queue_entry()

    assert ocs.submitted == []
    assert ocs.scheduled == []


def test_without_an_active_config_nothing_is_submitted(pending_entry, ocs):
    tasks.process_next_queue_entry()

    pending_entry.refresh_from_db()
    assert pending_entry.status == QueueEntry.Status.PENDING
    assert ocs.submitted == []


class TestSpacingHolds:
    """Spacing has to hold against every caller, not just the run that scheduled it.

    Beat calls this task every 60 seconds and the queue page has a "process now" button.
    While pacing was only a `countdown` on the follow-up task, a config asking for 180
    seconds between alignments got none: beat claimed and submitted the next entry twice
    over before the countdown came due.
    """

    @pytest.fixture(autouse=True)
    def _clear_spacing_hold(self):
        cache.delete(tasks.SPACING_HOLD_KEY)
        yield
        cache.delete(tasks.SPACING_HOLD_KEY)

    @pytest.fixture
    def two_pending(self, user, make_sample):
        def _entry(fastq_name):
            return QueueEntry.objects.create(
                sample=make_sample(fastq_name),
                stage=Stage.ALIGN,
                requested_by=user,
                modality="MTX",
                modality_source=QueueEntry.ModalitySource.INFERRED,
                notify_email="bicore@alleninstitute.org",
                command_args=["ocs", "fastqs", "align", "tenx-arc"],
                command="ocs fastqs align tenx-arc",
                spacing=180,
            )

        return [_entry("READY-1"), _entry("READY-2")]

    def test_a_second_run_inside_the_spacing_submits_nothing(self, active_config, two_pending, ocs):
        tasks.process_next_queue_entry()
        tasks.process_next_queue_entry()  # beat, 60 seconds later

        assert len(ocs.submitted) == 1
        assert QueueEntry.objects.filter(status=QueueEntry.Status.PENDING).count() == 1

    def test_the_hold_expires_with_the_spacing(self, active_config, two_pending, ocs):
        tasks.process_next_queue_entry()
        cache.delete(tasks.SPACING_HOLD_KEY)  # the 180 seconds have passed

        tasks.process_next_queue_entry()

        assert len(ocs.submitted) == 2

    def test_the_capacity_check_is_not_even_reached_while_spacing_holds(
        self, active_config, two_pending, ocs
    ):
        """The hold is checked before OCS is counted, so a paced queue costs no DynamoDB."""
        tasks.process_next_queue_entry()
        calls_after_first = ocs.count_calls

        tasks.process_next_queue_entry()

        assert ocs.count_calls == calls_after_first

    def test_a_refusal_is_not_spaced(self, active_config, two_pending, ocs, monkeypatch):
        """A refused command consumed no OCS capacity, so there is nothing to pace."""
        monkeypatch.setattr(
            tasks.cli, "submit", lambda command_args: (_ for _ in ()).throw(OCSSubmissionError("no"))
        )

        tasks.process_next_queue_entry()

        assert not cache.get(tasks.SPACING_HOLD_KEY)


def test_an_unexpected_fault_is_recorded_and_re_raised(active_config, pending_entry, ocs, monkeypatch):
    """A bug on our side is not an OCS refusal: the entry must not be left in SUBMITTING,
    and the exception must still reach the worker log rather than being filed as a job that
    failed for a reason the user can act on."""

    def explode(command_args):
        raise KeyError("command_args")

    monkeypatch.setattr(tasks.cli, "submit", explode)

    with pytest.raises(KeyError):
        tasks.process_next_queue_entry()

    pending_entry.refresh_from_db()
    assert pending_entry.status == QueueEntry.Status.FAILED
    assert "worker log" in pending_entry.error_message
