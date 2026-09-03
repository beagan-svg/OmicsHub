from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.workflow_engine import manifest_service
from apps.workflow_engine.models import WorkflowConfig


class WorkflowConfigSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField()

    class Meta:
        model = WorkflowConfig
        fields = ["id", "name", "raw", "data", "uploaded_by", "uploaded_at", "is_active"]


# The `name` column, which the filename falls back to.
NAME_MAX_LENGTH = 255


class WorkflowConfigUploadSerializer(serializers.Serializer):
    """Validate a JSONC manifest before storing it."""

    file = serializers.FileField()
    name = serializers.CharField(required=False, max_length=NAME_MAX_LENGTH)

    def validate_file(self, uploaded):
        if uploaded.size > manifest_service.MAX_CONFIG_BYTES:
            raise serializers.ValidationError(
                f"Config file is {uploaded.size} bytes; the limit is {manifest_service.MAX_CONFIG_BYTES}."
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
            return manifest_service.create_config(
                raw=raw,
                name=name,
                user=self.context["request"].user,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
