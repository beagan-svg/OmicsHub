"""The scheduled tasks that keep the mirror in step with OCS.

The guard these mostly exist for is the no-active-config check. Without a config there is
no set of batch prefixes, and an empty set reaches `_prune_out_of_scope` as "nothing is in
scope" , which, before that function refused it, meant deleting the entire mirror.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache

from apps.catalog import tasks
from apps.catalog.services import sync
from apps.workflows.models import WorkflowConfig

pytestmark = pytest.mark.django_db


@pytest.fixture
def active_config(db, user):
    return WorkflowConfig.objects.create(
        name="active",
        raw="",
        data={"workflows": {"MTX": {}, "RTX": {}}},
        uploaded_by=user,
        is_active=True,
    )


@pytest.fixture
def calls(monkeypatch):
    """Record what the tasks hand to the sync layer, without running it."""
    recorded = []
    monkeypatch.setattr(
        sync, "sync_all_stage_statuses", lambda batch_prefixes: recorded.append(batch_prefixes) or "swept"
    )
    monkeypatch.setattr(
        sync, "sync_all_samples", lambda batch_prefixes: recorded.append(batch_prefixes) or "mirrored"
    )
    return recorded


class TestScope:
    def test_the_sweep_runs_over_the_active_configs_prefixes(self, active_config, calls):
        assert tasks.sync_all_stage_statuses() == "swept"
        # ATX rides on MTX: it has no workflow of its own but must still be mirrored.
        assert calls == [{"MTX", "ATX", "RTX"}]

    def test_the_metadata_sweep_runs_over_the_same_prefixes(self, active_config, calls):
        assert tasks.sync_all_metadata() == "mirrored"

        assert calls == [{"MTX", "ATX", "RTX"}]

    def test_an_inactive_config_does_not_count(self, active_config, calls):
        WorkflowConfig.objects.update(is_active=False)

        assert tasks.sync_all_metadata() is None
        assert calls == []


class TestNoActiveConfig:
    """The only thing between an empty prefix set and a prune of the whole mirror."""

    def test_the_stage_status_sweep_returns_without_calling_sync(self, calls):
        assert tasks.sync_all_stage_statuses() is None

        assert calls == []

    def test_the_metadata_sweep_returns_without_calling_sync(self, calls):
        assert tasks.sync_all_metadata() is None

        assert calls == []

    def test_the_metadata_sweep_never_reaches_the_prune(self, make_sample, monkeypatch):
        """End to end, against the real sync: no config must not empty the mirror."""
        make_sample("KEEP-ME-1")
        monkeypatch.setattr(sync.dynamodb, "scan_metadata", lambda batch_prefixes=None: iter([]))

        assert tasks.sync_all_metadata() is None
        assert sync.Sample.objects.filter(fastq_name="KEEP-ME-1").exists()

    def test_the_sweep_releases_its_lock_on_the_way_out(self, calls):
        tasks.sync_all_stage_statuses()

        assert cache.get(tasks.SWEEP_LOCK_KEY) is None


class TestOverlapGuard:
    """Beat fires the sweep every 300s against a 900s time limit, so a slow sweep would
    otherwise run alongside itself with both copies writing the same rows."""

    def test_a_second_sweep_is_skipped_while_one_is_running(self, active_config, monkeypatch):
        ran = []

        def slow_sweep(batch_prefixes):
            # The reentrant call is what a beat tick during a slow sweep looks like.
            ran.append(tasks.sync_all_stage_statuses())
            return "outer"

        monkeypatch.setattr(sync, "sync_all_stage_statuses", slow_sweep)

        assert tasks.sync_all_stage_statuses() == "outer"
        assert ran == [None], "the overlapping tick must not have run the sweep"

    def test_the_lock_is_released_even_when_the_sweep_raises(self, active_config, monkeypatch):
        def boom(batch_prefixes):
            raise RuntimeError("OCS is down")

        monkeypatch.setattr(sync, "sync_all_stage_statuses", boom)

        with pytest.raises(RuntimeError):
            tasks.sync_all_stage_statuses()

        assert cache.get(tasks.SWEEP_LOCK_KEY) is None, "a failed sweep must not wedge the schedule"

    def test_the_lock_expires_on_its_own(self):
        """A worker killed at the task time limit never reaches its `finally`, so the lock
        has to time out rather than block every sweep from then on."""
        assert tasks.SWEEP_LOCK_TIMEOUT >= 900


class TestTaskOptions:
    def test_both_tasks_ack_late(self):
        """Both reread OCS from scratch and write only what moved, so redelivering one
        after a lost worker is safe , and losing the message silently is not."""
        assert tasks.sync_all_stage_statuses.acks_late
        assert tasks.sync_all_metadata.acks_late
