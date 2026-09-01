from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.sample_catalog import ocs_sync as sync
from apps.sample_catalog.models import Sample
from apps.sample_catalog.serializers import SampleSerializer, SyncRequestSerializer

FILTER_FIELDS = ("batch_name_from_vendor", "organism_common_name", "library_prep_method_name")


class SampleViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """List locally synced OCS fastq samples and refresh them with `sync`."""

    serializer_class = SampleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Sample.objects.prefetch_related("stage_statuses")
        for field in FILTER_FIELDS:
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        fastq_name = self.request.query_params.get("fastq_name")
        if fastq_name:
            queryset = queryset.filter(fastq_name__icontains=fastq_name)
        return queryset

    @action(detail=False, methods=["post"])
    def sync(self, request):
        """Sync metadata and stage status for a batch name from the vendor or fastq names."""
        sync_request_serializer = SyncRequestSerializer(data=request.data)
        sync_request_serializer.is_valid(raise_exception=True)

        batch_name = sync_request_serializer.validated_data.get("batch_name_from_vendor")
        if batch_name:
            samples = sync.sync_batch(batch_name)
        else:
            samples = sync.sync_fastq_names(sync_request_serializer.validated_data["fastq_names"])

        refreshed = Sample.objects.filter(pk__in=[s.pk for s in samples]).prefetch_related("stage_statuses")
        return Response(SampleSerializer(refreshed, many=True).data, status=status.HTTP_200_OK)
