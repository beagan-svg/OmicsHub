"""Admin guards on the config that every submission is built from."""

from __future__ import annotations

import pytest
from django.contrib.admin.sites import AdminSite
from django.urls import reverse

from apps.workflow_engine.admin import WorkflowConfigAdmin
from apps.workflow_engine.models import WorkflowConfig

pytestmark = pytest.mark.django_db


@pytest.fixture
def config_admin():
    return WorkflowConfigAdmin(WorkflowConfig, AdminSite())


def make_config(user, *, is_active: bool) -> WorkflowConfig:
    name = "active" if is_active else "spare"
    return WorkflowConfig.objects.create(name=name, raw="{}", data={}, uploaded_by=user, is_active=is_active)


def test_the_active_config_cannot_be_deleted(config_admin, user):
    """apps/submission_queue reads it on every tick, so deleting it stops the queue."""
    assert config_admin.has_delete_permission(None, make_config(user, is_active=True)) is False


def test_an_inactive_config_can_be_deleted(config_admin, user):
    assert config_admin.has_delete_permission(None, make_config(user, is_active=False)) is True


@pytest.mark.django_db
def test_changelist_renders_at_the_configured_admin_path(admin_client, user):
    """Also the check that the admin still resolves after being moved off /admin/."""
    make_config(user, is_active=True)

    response = admin_client.get(reverse("admin:workflows_workflowconfig_changelist"))

    assert response.status_code == 200
