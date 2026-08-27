from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.submission_queue.models import QueueEntry


@pytest.fixture
def other_user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="colleague", email="colleague@alleninstitute.org", password="password"
    )


@pytest.fixture
def other_client(other_user):
    client = Client()
    client.force_login(other_user)
    return client


@pytest.fixture
def staff_user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="curator", email="curator@alleninstitute.org", password="password", is_staff=True
    )


@pytest.fixture
def staff_client(staff_user):
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def submit(logged_in):
    def _submit(fastq_names, **extra):
        return logged_in.post(
            reverse("web_ui:submit-confirm"), {"fastq_names": list(fastq_names), **extra}, follow=True
        )

    return _submit


@pytest.fixture
def review(logged_in):
    def _review(fastq_names, **extra):
        return logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": list(fastq_names), **extra})

    return _review


@pytest.fixture
def queued(logged_in, active_config, make_sample):
    def _queue(fastq_name="READY-1", **sample_kwargs):
        make_sample(fastq_name, **sample_kwargs)
        logged_in.post(reverse("web_ui:submit-confirm"), {"fastq_names": [fastq_name]})
        return QueueEntry.objects.get(sample__fastq_name=fastq_name)

    return _queue


@pytest.fixture
def queued_entry(logged_in, active_config, make_sample):
    def _queued(fastq_name="READY-1", *, owner_client=None, **sample_kwargs):
        make_sample(fastq_name, **sample_kwargs)
        (owner_client or logged_in).post(reverse("web_ui:submit-confirm"), {"fastq_names": [fastq_name]})
        return QueueEntry.objects.get(sample__fastq_name=fastq_name)

    return _queued
