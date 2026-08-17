"""Admin actions that guard against submitting the same job twice."""

from __future__ import annotations

import pytest
from django.contrib.admin.sites import AdminSite
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.sample_catalog.models import Stage
from apps.submission_queue.admin import QueueEntryAdmin
from apps.submission_queue.models import QueueEntry

pytestmark = pytest.mark.django_db


@pytest.fixture
def model_admin():
    return QueueEntryAdmin(QueueEntry, AdminSite())


@pytest.fixture
def request_with_messages(user):
    request = RequestFactory().post("/admin/")
    request.user = user
    request._messages = type("Storage", (), {"add": lambda self, *args, **kwargs: None})()
    return request


@pytest.fixture
def entry(make_sample, user):
    def _make(status):
        return QueueEntry.objects.create(
            sample=make_sample(f"SAMPLE-{status}"),
            stage=Stage.ALIGN,
            requested_by=user,
            modality="MTX",
            modality_source=QueueEntry.ModalitySource.INFERRED,
            notify_email="bicore@alleninstitute.org",
            command_args=["ocs"],
            command="ocs",
            spacing=180,
            status=status,
            submitted_at=timezone.now() if status == QueueEntry.Status.SUBMITTED else None,
        )

    return _make


def test_requeue_returns_failed_entries_to_the_queue(model_admin, request_with_messages, entry):
    failed = entry(QueueEntry.Status.FAILED)

    model_admin.requeue_entries(request_with_messages, QueueEntry.objects.all())

    failed.refresh_from_db()
    assert failed.status == QueueEntry.Status.PENDING


def test_requeue_skips_submitted_entries(model_admin, request_with_messages, entry):
    """They already have a demand at OCS."""
    submitted = entry(QueueEntry.Status.SUBMITTED)

    model_admin.requeue_entries(request_with_messages, QueueEntry.objects.all())

    submitted.refresh_from_db()
    assert submitted.status == QueueEntry.Status.SUBMITTED


def test_requeue_skips_stranded_entries(model_admin, request_with_messages, entry):
    """Nobody knows yet whether these reached OCS , bulk requeueing could duplicate a job."""
    stranded = entry(QueueEntry.Status.STRANDED)

    model_admin.requeue_entries(request_with_messages, QueueEntry.objects.all())

    stranded.refresh_from_db()
    assert stranded.status == QueueEntry.Status.STRANDED


def test_changelist_does_not_query_once_per_entry(admin_client, make_sample, django_user_model):
    """list_display dereferences `sample` and `requested_by` on every row.

    Both are covered by list_select_related; drop either and the query count grows with
    the queue. Compared render-to-render rather than pinned to a number, so a Django
    upgrade that adds a query of its own does not fail this.
    """

    def queue_one(index):
        QueueEntry.objects.create(
            sample=make_sample(f"SAMPLE-LIST-{index}"),
            stage=Stage.ALIGN,
            requested_by=django_user_model.objects.create_user(username=f"requester-{index}"),
            modality="MTX",
            modality_source=QueueEntry.ModalitySource.INFERRED,
            notify_email="bicore@alleninstitute.org",
            command_args=["ocs"],
            command="ocs",
            spacing=180,
        )

    url = reverse("admin:queueing_queueentry_changelist")
    admin_client.get(url)  # Warm anything cached per process, e.g. content types.

    queue_one(0)
    with CaptureQueriesContext(connection) as one_row:
        admin_client.get(url)

    for index in range(1, 4):
        queue_one(index)
    with CaptureQueriesContext(connection) as four_rows:
        admin_client.get(url)

    assert len(four_rows) == len(one_row)


def test_cancel_only_affects_pending_entries(model_admin, request_with_messages, entry):
    pending = entry(QueueEntry.Status.PENDING)
    submitted = entry(QueueEntry.Status.SUBMITTED)

    model_admin.cancel_entries(request_with_messages, QueueEntry.objects.all())

    pending.refresh_from_db()
    submitted.refresh_from_db()
    assert pending.status == QueueEntry.Status.CANCELLED
    assert submitted.status == QueueEntry.Status.SUBMITTED
