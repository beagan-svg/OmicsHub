from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from apps.workflow_engine.models import WorkflowConfig
from apps.workflow_engine.serializers import WorkflowConfigSerializer, WorkflowConfigUploadSerializer


class WorkflowConfigViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Upload and activate the manifest that drives every submission.

    Admin-only: the active config decides what commands run against real OCS capacity for
    everyone, so it is not something an ordinary queue user changes.
    """

    queryset = WorkflowConfig.objects.select_related("uploaded_by")
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action == "create":
            return WorkflowConfigUploadSerializer
        return WorkflowConfigSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        return Response(WorkflowConfigSerializer(config).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        config = self.get_object()
        config.activate()
        return Response(WorkflowConfigSerializer(config).data)
