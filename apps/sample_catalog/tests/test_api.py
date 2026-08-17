"""Listing samples and pulling them from OCS."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.sample_catalog.services import sync as sync_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client(user):
    api_client = APIClient()
    api_client.force_authenticate(user)
    return api_client


def test_lists_samples_with_their_stage_status(api_client, make_sample):
    make_sample("READY-1", align="IN_PROGRESS")

    body = api_client.get("/api/samples/").json()

    assert body["count"] == 1
    statuses = {entry["stage"]: entry["status"] for entry in body["results"][0]["stage_statuses"]}
    assert statuses["align"] == "IN_PROGRESS"


def test_filters_by_batch(api_client, make_sample):
    make_sample("A-1", batch_name_from_vendor="MTX-22068")
    make_sample("B-1", batch_name_from_vendor="RTX-34056")

    body = api_client.get("/api/samples/?batch_name_from_vendor=MTX-22068").json()

    assert [result["fastq_name"] for result in body["results"]] == ["A-1"]


def test_sync_pulls_a_batch_from_ocs(api_client, monkeypatch, make_sample):
    called = {}

    def fake_sync_batch(batch_name_from_vendor):
        called["batch"] = batch_name_from_vendor
        return [make_sample("NEW-1", batch_name_from_vendor=batch_name_from_vendor)]

    monkeypatch.setattr(sync_service, "sync_batch", fake_sync_batch)

    response = api_client.post("/api/samples/sync/", {"batch_name_from_vendor": "MTX-22068"}, format="json")

    assert response.status_code == 200
    assert called["batch"] == "MTX-22068"
    assert [entry["fastq_name"] for entry in response.json()] == ["NEW-1"]


def test_sync_requires_exactly_one_selector(api_client):
    response = api_client.post(
        "/api/samples/sync/",
        {"batch_name_from_vendor": "MTX-22068", "fastq_names": ["A"]},
        format="json",
    )

    assert response.status_code == 400


def test_authentication_is_required():
    assert APIClient().get("/api/samples/").status_code in (401, 403)
