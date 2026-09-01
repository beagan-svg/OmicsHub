"""Every API failure comes back in one shape: {"error": {"message": {field: [msg]}}}."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client(user):
    api_client = APIClient()
    api_client.force_authenticate(user)
    return api_client


def test_validation_errors_are_wrapped(api_client, make_sample):
    response = api_client.post("/api/queue/plan/", {}, format="json")

    assert response.status_code == 400
    assert isinstance(response.json()["error"]["message"], dict)


def test_a_serializer_validate_error_lands_under_the_same_key_as_a_view_raised_one(api_client):
    """A non-field error from a serializer's own `validate()` (this one, from
    `require_exactly_one_field`) must land under the same key a plain
    `raise ValidationError("...")` in view code would use -- otherwise a client reading one
    key would silently miss the other, even though both mean "an error not about one field".
    """
    response = api_client.post("/api/queue/plan/", {}, format="json")

    message = response.json()["error"]["message"]
    assert "non_field_errors" not in message
    assert isinstance(message["detail"], list)


def test_field_errors_keep_their_structure(api_client):
    """A api_client has to know which field failed, so the shape inside is preserved."""
    response = api_client.post("/api/samples/sync/", {"fastq_names": "not-a-list"}, format="json")

    message = response.json()["error"]["message"]
    assert isinstance(message["fastq_names"], list)


def test_not_found_is_wrapped_too(api_client):
    response = api_client.get("/api/queue/999999/")

    assert response.status_code == 404
    assert isinstance(response.json()["error"]["message"]["detail"], list)


def test_permission_errors_are_wrapped(user):
    """A non-staff user hitting an admin-only endpoint."""
    api_client = APIClient()
    api_client.force_authenticate(user)

    response = api_client.get("/api/configs/")

    assert response.status_code == 403
    assert isinstance(response.json()["error"]["message"]["detail"], list)


def test_unauthenticated_requests_are_wrapped():
    response = APIClient().get("/api/queue/")

    assert response.status_code in (401, 403)
    assert isinstance(response.json()["error"]["message"]["detail"], list)
