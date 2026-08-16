from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.catalog.models import Sample
from apps.catalog.serializers import SampleSerializer, SyncRequestSerializer
from apps.catalog.services import sync

FILTER_FIELDS = ("batch_name_from_vendor", "organism_common_name", "library_prep_method_name")


class SampleViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """List fastq samples mirrored from OCS. Refresh them with `sync`."""

    serializer_class = SampleSerializer

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
        """Load metadata and stage status for a vendor batch or fastq names."""
        serializer = SyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        batch_name = serializer.validated_data.get("batch_name_from_vendor")
        if batch_name:
            samples = sync.sync_batch(batch_name)
        else:
            samples = sync.sync_fastq_names(serializer.validated_data["fastq_names"])

        refreshed = Sample.objects.filter(pk__in=[s.pk for s in samples]).prefetch_related("stage_statuses")
        return Response(SampleSerializer(refreshed, many=True).data, status=status.HTTP_200_OK)
