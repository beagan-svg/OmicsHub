"""Create and validate workflow manifests.

The API serializer and web view share these operations. Both paths parse, validate, and
store the uploaded manifest.
"""

from __future__ import annotations

from apps.workflow_engine import config_loader
from apps.workflow_engine.models import WorkflowConfig


def create_config(*, raw: str, name: str, user) -> WorkflowConfig:
    """Parse and validate a JSONC manifest, then store it inactive.

    Raises django.core.exceptions.ValidationError if the config could not drive a
    submission. Uploading never activates: switching what everyone's jobs are built from
    is a separate, deliberate step.
    """
    data = config_loader.load_jsonc(raw)
    config_loader.validate(data)
    return WorkflowConfig.objects.create(name=name, raw=raw, data=data, uploaded_by=user)
