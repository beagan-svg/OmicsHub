from __future__ import annotations

from apps.workflows import modality


def test_available_modalities_lists_configured_workflows(config):
    assert modality.available_modalities(config) == ["MTX", "RTX"]
