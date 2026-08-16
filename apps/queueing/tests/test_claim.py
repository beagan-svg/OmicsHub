"""Round-robin claiming: one user's large batch must not starve another user."""

from __future__ import annotations

import datetime as dt
import threading
from contextlib import contextmanager

import pytest
from django.db import connections, transaction
from django.utils import timezone

from apps.catalog.models import Stage
from apps.queueing.models import QueueEntry
from apps.queueing.services.claim import claim_next_entry

pytestmark = pytest.mark.django_db


@pytest.fixture
def make_entry(make_sample):
    def _make(user, fastq_name, *, status=QueueEntry.Status.PENDING, submitted_at=None):
        return QueueEntry.objects.create(
            sample=make_sample(fastq_name),
            stage=Stage.ALIGN,
            requested_by=user,
            modality="MTX",
            modality_source=QueueEntry.ModalitySource.INFERRED,
            notify_email="bicore@alleninstitute.org",
            command_args=["ocs"],
            command="ocs",
            spacing=180,
            status=status,
            submitted_at=submitted_at,
        )

    return _make


@pytest.fixture
def other_user(django_user_model):
    return django_user_model.objects.create_user(username="second", email="second@example.org")


def test_returns_none_when_nothing_is_pending(db):
    assert claim_next_entry() is None


def test_claims_the_oldest_entry_for_a_single_user(user, make_entry):
    first = make_entry(user, "FIRST")
    make_entry(user, "SECOND")

    assert claim_next_entry().pk == first.pk


def test_claiming_marks_the_entry_submitting(user, make_entry):
    make_entry(user, "FIRST")

    claimed = claim_next_entry()

    claimed.refresh_from_db()
    assert claimed.status == QueueEntry.Status.SUBMITTING


def test_claiming_stamps_claimed_at(user, make_entry):
    """The reconciler times abandonment from this, so a claim without it is invisible."""
    make_entry(user, "FIRST")

    claimed = claim_next_entry()

    claimed.refresh_from_db()
    assert claimed.claimed_at is not None


def test_alternates_between_users(user, other_user, make_entry):
    """The user who submitted least recently goes next, so a big batch cannot hog capacity."""
    make_entry(user, "A-1")
    make_entry(user, "A-2")
    make_entry(other_user, "B-1")

    first = claim_next_entry()
    first.status = QueueEntry.Status.SUBMITTED
    first.submitted_at = timezone.now()
    first.save()

    second = claim_next_entry()

    assert {first.requested_by_id, second.requested_by_id} == {user.pk, other_user.pk}


def test_a_user_who_has_never_submitted_goes_first(user, other_user, make_entry):
    make_entry(user, "OLD", status=QueueEntry.Status.SUBMITTED, submitted_at=timezone.now())
    make_entry(user, "A-1")
    make_entry(other_user, "B-1")

    assert claim_next_entry().requested_by_id == other_user.pk


def test_the_longest_waiting_user_goes_first(user, other_user, make_entry):
    now = timezone.now()
    make_entry(
        user,
        "A-OLD",
        status=QueueEntry.Status.SUBMITTED,
        submitted_at=now - dt.timedelta(hours=2),
    )
    make_entry(
        other_user,
        "B-RECENT",
        status=QueueEntry.Status.SUBMITTED,
        submitted_at=now - dt.timedelta(minutes=1),
    )
    make_entry(user, "A-1")
    make_entry(other_user, "B-1")

    assert claim_next_entry().requested_by_id == user.pk


def test_skips_entries_that_are_not_pending(user, make_entry):
    make_entry(user, "DONE", status=QueueEntry.Status.SUBMITTED, submitted_at=timezone.now())
    make_entry(user, "CANCELLED", status=QueueEntry.Status.CANCELLED)
    pending = make_entry(user, "PENDING")

    assert claim_next_entry().pk == pending.pk


class TestTwoWorkers:
    """The reason this suite runs on Postgres rather than SQLite.

    `claim_next_entry` locks the row it is about to claim with `select_for_update
    (skip_locked=True)`. Every other test in this file claims serially inside one
    transaction, where that lock is a no-op , remove it and they all still pass. These
    hold a real lock from a second connection, which is the only way the skipping is
    exercised at all.
    """

    @pytest.fixture
    def held(self):
        """Lock one entry from another connection, as a second worker mid-claim would."""

        @contextmanager
        def _hold(entry):
            done = threading.Event()
            locked = threading.Event()

            def worker():
                try:
                    with transaction.atomic():
                        QueueEntry.objects.select_for_update().get(pk=entry.pk)
                        locked.set()
                        done.wait(timeout=10)
                finally:
                    # This thread owns its own connection, and a connection still open at
                    # the end of the run blocks the test database being dropped — which
                    # then fails the *next* run at CREATE DATABASE, not this one.
                    connections.close_all()

            thread = threading.Thread(target=worker)
            thread.start()
            locked.wait(timeout=10)
            try:
                yield
            finally:
                done.set()
                thread.join(timeout=10)

        return _hold

    @pytest.mark.django_db(transaction=True)
    def test_a_locked_entry_is_passed_over_rather_than_waited_for(self, user, make_entry, held):
        first = make_entry(user, "A-1")
        second = make_entry(user, "A-2")

        with held(first):
            claimed = claim_next_entry()

        assert claimed.pk == second.pk

    @pytest.mark.django_db(transaction=True)
    def test_nothing_is_claimed_twice(self, user, make_entry, held):
        only = make_entry(user, "A-1")

        with held(only):
            assert claim_next_entry() is None

        only.refresh_from_db()
        assert only.status == QueueEntry.Status.PENDING
