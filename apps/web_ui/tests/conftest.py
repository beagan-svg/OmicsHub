from __future__ import annotations

from pathlib import Path

import pytest
from django.test import Client
from django.urls import reverse

from apps.ocs_integration import log_credentials
from apps.submission_queue.models import QueueEntry

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def messages_in(response) -> str:
    return response.content.decode()


class FakeStsClient:
    """A stand-in for a boto3 STS client, returning a fixed fake identity."""

    def get_caller_identity(self):
        return {
            "UserId": "AID1",
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/x/y",
        }


class FakeStsSession:
    """A stand-in for a boto3 Session that only ever hands out FakeStsClient."""

    def client(self, service_name, **kwargs):
        assert service_name == "sts"
        return FakeStsClient()


def stub_valid_sts(monkeypatch):
    """Patch one level below validate_credentials, not validate_credentials itself, so
    its real caching side effect actually runs -- a test that replaces
    validate_credentials wholesale would see job_credentials_submit return "valid" but
    leave the cache empty, since the caching happens inside the function being replaced.
    """
    monkeypatch.setattr(log_credentials, "_session", lambda *a: FakeStsSession())


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
def queued_entry(logged_in, active_config, make_sample):
    def _queued(fastq_name="READY-1", *, owner_client=None, **sample_kwargs):
        make_sample(fastq_name, **sample_kwargs)
        (owner_client or logged_in).post(reverse("web_ui:submit-confirm"), {"fastq_names": [fastq_name]})
        return QueueEntry.objects.get(sample__fastq_name=fastq_name)

    return _queued
