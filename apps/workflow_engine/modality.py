"""Return modalities covered by a workflow manifest.

A modality is a workflow the manifest defines, such as MTX or RTX. Nothing outside that set can
be queued, so the callers use this both to offer a choice and to reject one.
"""

from __future__ import annotations


def available_modalities(config: dict) -> list[str]:
    """Return modalities a user may choose from in the manifest."""
    return sorted(config["workflows"])
