"""Create and validate workflow manifests.

The API serializer and web view share these operations. Both paths parse, validate, and
store the uploaded manifest.
"""

from __future__ import annotations

from apps.workflow_engine import config_loader
from apps.workflow_engine.models import WorkflowConfig

# A real config is tens of kilobytes. The whole file is held in memory and then stored
# twice, as raw text and parsed JSON, so uploads are capped. Both upload paths (the web
# form and the API serializer) enforce this same limit; DATA_UPLOAD_MAX_MEMORY_SIZE does
# not apply to file fields.
MAX_CONFIG_BYTES = 2 * 1024 * 1024


def create_config(*, raw: str, name: str, user) -> WorkflowConfig:
    """Parse and validate a JSONC manifest, then store it inactive.

    Raises django.core.exceptions.ValidationError if the config could not drive a
    submission. Uploading never activates: switching what everyone's jobs are built from
    is a separate, deliberate step.
    """
    data = config_loader.load_jsonc(raw)
    config_loader.validate(data)
    return WorkflowConfig.objects.create(name=name, raw=raw, data=data, uploaded_by=user)
