"""Database-level guarantees the services rely on."""

from __future__ import annotations

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from apps.sample_catalog.models import Stage, StageStatus
from apps.submission_queue.models import QueueEntry

pytestmark = pytest.mark.django_db


def make_entry(sample, user, **overrides):
    fields = {
        "sample": sample,
        "stage": Stage.ALIGN,
        "requested_by": user,
        "modality": "MTX",
        "modality_source": QueueEntry.ModalitySource.INFERRED,
        "notify_email": "bicore@alleninstitute.org",
        "command_args": ["ocs"],
        "command": "ocs",
        "spacing": 180,
    }
    return QueueEntry.objects.create(**{**fields, **overrides})


def test_a_sample_stage_cannot_be_pending_twice(make_sample, user):
    """The backstop behind the enqueue check, for two requests racing each other."""
    sample = make_sample("READY-1")
    make_entry(sample, user)

    with pytest.raises(IntegrityError):
        make_entry(sample, user)


def test_the_same_stage_may_be_queued_again_once_the_first_is_done(make_sample, user):
    sample = make_sample("READY-1")
    make_entry(sample, user, status=QueueEntry.Status.FAILED)

    make_entry(sample, user)

    assert QueueEntry.objects.count() == 2


def test_deleting_a_sample_cannot_destroy_job_history(make_sample, user):
    """A submitted entry is the only local record that a job reached OCS."""
    sample = make_sample("READY-1")
    make_entry(sample, user, status=QueueEntry.Status.SUBMITTED, demand_id="demand-123")

    with pytest.raises(ProtectedError):
        sample.delete()

    assert QueueEntry.objects.count() == 1


def test_stage_statuses_do_go_with_their_sample(make_sample, user):
    """Unlike queue entries, these are derived and mean nothing on their own."""
    sample = make_sample("READY-1", align="COMPLETED")
    assert StageStatus.objects.count() == 2

    sample.delete()

    assert StageStatus.objects.count() == 0


def test_both_stages_may_be_pending_for_one_sample(make_sample, user):
    sample = make_sample("READY-1")
    make_entry(sample, user, stage=Stage.ALIGN)

    make_entry(sample, user, stage=Stage.POST_ALIGN)

    assert QueueEntry.objects.count() == 2
