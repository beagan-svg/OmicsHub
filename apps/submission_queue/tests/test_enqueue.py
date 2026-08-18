"""Turning a confirmed plan into queue entries."""

from __future__ import annotations

import pytest

from apps.sample_catalog.models import Stage
from apps.submission_queue.models import QueueEntry
from apps.submission_queue.queue_entries import enqueue
from apps.submission_queue.queue_planning import build_plan

pytestmark = pytest.mark.django_db

EMAIL = "bicore@alleninstitute.org"


class TestADoubleConfirm:
    """Two confirms of one plan land as "already queued", not as a 500.

    `one_pending_entry_per_sample_stage` is what actually decides; the pre-read is only
    how the second one is reported.
    """

    def test_the_second_confirm_reports_rather_than_queues(self, config, user, make_sample):
        sample = make_sample("TWICE-1")
        plan = build_plan(samples=[sample], config=config, email=EMAIL)

        first = enqueue(plan=plan, user=user, notify_email=EMAIL)
        second = enqueue(plan=plan, user=user, notify_email=EMAIL)

        assert len(first.created) == 1
        assert not second.created
        assert [entry.sample.fastq_name for entry in second.already_queued] == ["TWICE-1"]
        assert QueueEntry.objects.filter(sample=sample, stage=Stage.ALIGN).count() == 1

    def test_a_row_lost_to_the_constraint_is_still_reported(self, config, user, make_sample):
        """The pre-read cannot see a row a concurrent confirm has not committed yet, so the
        IntegrityError is the real guard. Simulated by inserting behind the read."""
        sample = make_sample("RACE-1")
        plan = build_plan(samples=[sample], config=config, email=EMAIL)
        QueueEntry.objects.create(
            sample=sample,
            stage=Stage.ALIGN,
            requested_by=user,
            modality="MTX",
            modality_source=QueueEntry.ModalitySource.INFERRED,
            notify_email=EMAIL,
            command_args=["ocs"],
            command="ocs",
            spacing=180,
        )

        result = enqueue(plan=plan, user=user, notify_email=EMAIL)

        assert not result.created
        assert len(result.already_queued) == 1
