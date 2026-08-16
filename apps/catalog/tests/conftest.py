"""Fixtures and helpers shared by the catalog tests."""

from __future__ import annotations

import datetime as dt

import pytest

from apps.catalog.services import sync


def when(days_ago: float) -> str:
    """Return an OCS timestamp relative to the current time.

    Relative rather than fixed because status now depends on a demand's age: a demand that
    still says IN_PROGRESS a fortnight after its last update is read as abandoned, so a
    hard-coded date would quietly change meaning as it recedes.
    """
    return (dt.datetime.now(dt.UTC) - dt.timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


@pytest.fixture
def swept(monkeypatch):
    """Run the full stage-status sweep over one page of history and one of demands."""

    def _sweep(history, demands, batch_prefixes=frozenset({"MTX", "RTX"})):
        monkeypatch.setattr(sync.dynamodb, "scan_history", lambda: iter([history]))
        monkeypatch.setattr(sync.dynamodb, "scan_demands", lambda: iter([demands]))
        return sync.sync_all_stage_statuses(batch_prefixes=set(batch_prefixes))

    return _sweep
