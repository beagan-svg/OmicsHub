from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.workflows import services
from apps.workflows.models import WorkflowConfig


class WorkflowConfigSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField()

    class Meta:
        model = WorkflowConfig
        fields = ["id", "name", "raw", "data", "uploaded_by", "uploaded_at", "is_active"]


# A real config is tens of kilobytes. The whole file is held in memory and then stored
# twice — raw text and parsed JSON — so it is capped here; DATA_UPLOAD_MAX_MEMORY_SIZE
# does not apply to file fields.
MAX_CONFIG_BYTES = 2 * 1024 * 1024

# The `name` column, which the filename falls back to.
NAME_MAX_LENGTH = 255


class WorkflowConfigUploadSerializer(serializers.Serializer):
    """Validate a JSONC manifest before storing it."""

    file = serializers.FileField()
    name = serializers.CharField(required=False, max_length=NAME_MAX_LENGTH)

    def validate_file(self, uploaded):
        if uploaded.size > MAX_CONFIG_BYTES:
            raise serializers.ValidationError(
                f"Config file is {uploaded.size} bytes; the limit is {MAX_CONFIG_BYTES}."
            )
        return uploaded

    def create(self, validated_data):
        uploaded = validated_data["file"]
        try:
            raw = uploaded.read().decode("utf-8")
        except UnicodeDecodeError as error:
            raise serializers.ValidationError({"file": "Config file must be UTF-8 text."}) from error

        name = (validated_data.get("name") or uploaded.name or "")[:NAME_MAX_LENGTH]
        try:
            return services.create_config(
                raw=raw,
                name=name,
                user=self.context["request"].user,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
