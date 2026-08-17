"""Uploading and activating the config."""

from __future__ import annotations

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.workflow_engine import serializers
from apps.workflow_engine.models import WorkflowConfig

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_api_client(django_user_model):
    admin = django_user_model.objects.create_user(username="admin", email="admin@example.org", is_staff=True)
    client = APIClient()
    client.force_authenticate(admin)
    return client


def upload(config: dict, name: str = "config.jsonc") -> SimpleUploadedFile:
    body = "// main configuration\n" + json.dumps(config)
    return SimpleUploadedFile(name, body.encode(), content_type="application/json")


def test_uploading_stores_the_raw_file_and_the_parsed_config(staff_api_client, config):
    response = staff_api_client.post("/api/configs/", {"file": upload(config)}, format="multipart")

    assert response.status_code == 201
    stored = WorkflowConfig.objects.get()
    assert stored.raw.startswith("// main configuration")
    assert stored.data["job_settings"]["limit"] == 100


def test_an_invalid_config_is_rejected(staff_api_client, config):
    del config["status_mappings"]

    response = staff_api_client.post("/api/configs/", {"file": upload(config)}, format="multipart")

    assert response.status_code == 400
    assert not WorkflowConfig.objects.exists()


def test_organism_keys_are_expanded_on_upload(staff_api_client, config):
    config["references"] = {"macaque | macaque_nemestrina": {"RTX": "ref"}}
    config["probe_sets_by_organism"] = {"macaque | macaque_nemestrina": {"10xV4": "probes"}}

    staff_api_client.post("/api/configs/", {"file": upload(config)}, format="multipart")

    stored = WorkflowConfig.objects.get().data
    assert set(stored["references"]) == {"macaque", "macaque_nemestrina"}
    # Looked up through the same organism matching, so an unexpanded key here resolves the
    # probe set to "" rather than raising.
    assert set(stored["probe_sets_by_organism"]) == {"macaque", "macaque_nemestrina"}


class TestARejectedUpload:
    """This endpoint's whole job is validating a user-supplied file, so it answers 400."""

    def test_a_file_that_is_not_utf_8(self, staff_api_client, config):
        body = SimpleUploadedFile("config.jsonc", b"\xff\xfe{}", content_type="application/json")

        response = staff_api_client.post("/api/configs/", {"file": body}, format="multipart")

        assert response.status_code == 400
        assert not WorkflowConfig.objects.exists()

    def test_a_file_over_the_size_limit(self, staff_api_client):
        oversized = b"/* " + b"x" * serializers.MAX_CONFIG_BYTES + b" */"
        body = SimpleUploadedFile("config.jsonc", oversized, content_type="application/json")

        response = staff_api_client.post("/api/configs/", {"file": body}, format="multipart")

        assert response.status_code == 400
        assert not WorkflowConfig.objects.exists()

    def test_a_command_written_as_a_string(self, staff_api_client, config):
        """The one bad type that used to store cleanly and then submit garbage argv."""
        config["workflows"]["MTX"]["alignment_command_configs"][0]["command"] = "ocs fastqs align"

        response = staff_api_client.post("/api/configs/", {"file": upload(config)}, format="multipart")

        assert response.status_code == 400
        assert not WorkflowConfig.objects.exists()


def test_a_long_filename_is_truncated_to_the_column(staff_api_client, config):
    """The name falls back to the filename, and the column holds 255 characters."""
    name = "a" * 300 + ".jsonc"

    staff_api_client.post("/api/configs/", {"file": upload(config, name)}, format="multipart")

    assert len(WorkflowConfig.objects.get().name) == serializers.NAME_MAX_LENGTH


def test_a_new_config_starts_inactive(staff_api_client, config):
    staff_api_client.post("/api/configs/", {"file": upload(config)}, format="multipart")

    assert WorkflowConfig.objects.get().is_active is False


def test_activating_deactivates_the_previous_one(staff_api_client, config):
    first = staff_api_client.post(
        "/api/configs/", {"file": upload(config, "first.jsonc")}, format="multipart"
    ).json()
    second = staff_api_client.post(
        "/api/configs/", {"file": upload(config, "second.jsonc")}, format="multipart"
    ).json()

    staff_api_client.post(f"/api/configs/{first['id']}/activate/")
    staff_api_client.post(f"/api/configs/{second['id']}/activate/")

    assert list(WorkflowConfig.objects.filter(is_active=True).values_list("id", flat=True)) == [second["id"]]


def test_non_admins_cannot_upload(user, config):
    client = APIClient()
    client.force_authenticate(user)

    response = client.post("/api/configs/", {"file": upload(config)}, format="multipart")

    assert response.status_code == 403
