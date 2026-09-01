from rest_framework import serializers

from apps.sample_catalog.models import Sample, StageStatus


class StageStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = StageStatus
        fields = ["stage", "status", "demand_id", "last_update_time"]


class SampleSerializer(serializers.ModelSerializer):
    stage_statuses = StageStatusSerializer(many=True, read_only=True)

    class Meta:
        model = Sample
        fields = [
            "id",
            "fastq_name",
            "batch_name_from_vendor",
            "load_name",
            "library_prep_method_name",
            "organism_common_name",
            "sample_names",
            "studies",
            "stage_statuses",
            "synced_at",
        ]


def require_exactly_one_field(attrs, field_a: str, field_b: str) -> None:
    """Raise a validation error unless exactly one of two request fields was given."""
    if bool(attrs.get(field_a)) == bool(attrs.get(field_b)):
        raise serializers.ValidationError(f"Provide exactly one of {field_a} or {field_b}.")


class SyncRequestSerializer(serializers.Serializer):
    """Validate a request for one batch name from the vendor or fastq names."""

    batch_name_from_vendor = serializers.CharField(required=False)
    fastq_names = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        require_exactly_one_field(attrs, "batch_name_from_vendor", "fastq_names")
        return attrs
