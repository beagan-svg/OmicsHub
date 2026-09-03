from botocore.exceptions import BotoCoreError, ClientError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.sample_catalog import ocs_sync as sync
from apps.sample_catalog.models import FILTER_FIELDS, Sample
from apps.sample_catalog.serializers import SampleSerializer, SyncRequestSerializer


class OCSUnavailable(APIException):
    """Report an unreachable OCS as a gateway problem, matching the web UI's treatment."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Could not reach OCS. Nothing was synced."
    default_code = "ocs_unavailable"


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
        # OCS being unreachable is an expected external condition, reported the same way
        # the web UI's sync reports it, not an unhandled 500.
        try:
            if batch_name:
                samples = sync.sync_batch(batch_name)
            else:
                samples = sync.sync_fastq_names(sync_request_serializer.validated_data["fastq_names"])
        except (BotoCoreError, ClientError) as error:
            raise OCSUnavailable() from error

        refreshed = Sample.objects.filter(pk__in=[s.pk for s in samples]).prefetch_related("stage_statuses")
        return Response(SampleSerializer(refreshed, many=True).data, status=status.HTTP_200_OK)
