from __future__ import annotations

from apps.workflow_engine import modality


def test_available_modalities_lists_configured_workflows(config):
    assert modality.available_modalities(config) == ["MTX", "RTX"]
