from rest_framework import serializers

from apps.sample_catalog.models import Stage
from apps.sample_catalog.serializers import StageStatusSerializer
from apps.submission_queue.models import QueueEntry


class QueueEntrySerializer(serializers.ModelSerializer):
    fastq_name = serializers.CharField(source="sample.fastq_name", read_only=True)
    batch_name_from_vendor = serializers.CharField(source="sample.batch_name_from_vendor", read_only=True)
    requested_by = serializers.StringRelatedField()
    stage_statuses = StageStatusSerializer(source="sample.stage_statuses", many=True, read_only=True)

    class Meta:
        model = QueueEntry
        fields = [
            "id",
            "fastq_name",
            "batch_name_from_vendor",
            "stage",
            "requested_by",
            "modality",
            "modality_source",
            "notify_email",
            "batch_processing",
            "forced",
            "command",
            "spacing",
            "status",
            "demand_id",
            "error_message",
            "created_at",
            "submitted_at",
            "stage_statuses",
        ]
        # Output only. Every write goes through the planner.
        read_only_fields = fields


class SubmissionRequestSerializer(serializers.Serializer):
    """Validate the request body for previewing or confirming a submission.

    `modality` is the user's answer when it could not be inferred from the batch name;
    supplying it also overrides inference for every sample in the request.
    """

    # Capped because planning is synchronous: every name costs a config lookup and a
    # rendered command inside the request.
    fastq_names = serializers.ListField(child=serializers.CharField(), required=False, max_length=500)
    batch_name_from_vendor = serializers.CharField(required=False)
    modality = serializers.CharField(required=False)
    force = serializers.ChoiceField(
        choices=[Stage.ALIGN.value, Stage.POST_ALIGN.value],
        required=False,
    )
    batch_processing = serializers.BooleanField(default=False)
    notify_email = serializers.EmailField(required=False)

    def validate(self, attrs):
        if bool(attrs.get("fastq_names")) == bool(attrs.get("batch_name_from_vendor")):
            raise serializers.ValidationError("Provide exactly one of fastq_names or batch_name_from_vendor.")
        return attrs
