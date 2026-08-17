from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.sample_catalog.models import Sample
from apps.sample_catalog.services import pairing
from apps.submission_queue.models import QueueEntry
from apps.submission_queue.serializers import QueueEntrySerializer, SubmissionRequestSerializer
from apps.submission_queue.services import enqueue as enqueue_service
from apps.submission_queue.services import planning
from apps.workflow_engine.modality import available_modalities
from apps.workflow_engine.models import WorkflowConfig


class QueueViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """List queue entries and create or cancel submissions."""

    serializer_class = QueueEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = QueueEntry.objects.select_related("sample", "requested_by").prefetch_related(
            "sample__stage_statuses"
        )
        if not self.request.user.is_staff:
            queryset = queryset.filter(requested_by=self.request.user)
        entry_status = self.request.query_params.get("status")
        if entry_status:
            queryset = queryset.filter(status=entry_status)
        return queryset

    @action(detail=False, methods=["post"])
    def plan(self, request):
        """Return the commands that would be submitted without queueing them."""
        plan, _, config = self._build_plan(request)
        return Response(_serialize_plan(plan, config))

    def create(self, request, *args, **kwargs):
        """Confirm a plan and create its queue entries."""
        plan, params, config = self._build_plan(request)

        if plan.needs_modality:
            raise ValidationError(
                {
                    "modality": "Could not infer a modality for every sample. Choose one and resubmit.",
                    "modality_required": [skip.sample.fastq_name for skip in plan.needs_modality],
                    "available_modalities": available_modalities(config),
                }
            )

        result = enqueue_service.enqueue(
            plan=plan,
            user=request.user,
            notify_email=params["notify_email"],
            forced=bool(params.get("force")),
            batch_processing=params["batch_processing"],
        )

        return Response(
            {
                "created": QueueEntrySerializer(result.created, many=True).data,
                "already_queued": [entry.sample.fastq_name for entry in result.already_queued],
                "skipped": _serialize_skips(plan),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a pending queue entry."""
        entry = self.get_object()
        # Update only pending entries so the worker cannot claim this entry first.
        cancelled = QueueEntry.objects.filter(pk=entry.pk, status=QueueEntry.Status.PENDING).update(
            status=QueueEntry.Status.CANCELLED
        )
        if not cancelled:
            raise ValidationError(f"Only pending entries can be cancelled; this one is {entry.status}.")
        entry.refresh_from_db()
        return Response(QueueEntrySerializer(entry).data)

    def _config(self) -> WorkflowConfig:
        config = WorkflowConfig.objects.filter(is_active=True).first()
        if config is None:
            raise ValidationError("No active workflow config. Upload and activate one first.")
        return config

    def _build_plan(self, request):
        serializer = SubmissionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data

        config = self._config().data

        modality = params.get("modality")
        if modality and modality not in config["workflows"]:
            raise ValidationError(
                {"modality": f"Unknown modality. The config defines {available_modalities(config)}."}
            )

        notify_email = params.get("notify_email") or request.user.email
        if not notify_email:
            raise ValidationError(
                {"notify_email": "Required. Your account has no email address for OCS to notify."}
            )

        samples = self._samples(params)
        plan = planning.build_plan(
            samples=samples,
            config=config,
            email=notify_email,
            modality=modality,
            force=params.get("force"),
            batch_processing=params["batch_processing"],
        )
        return plan, {**params, "notify_email": notify_email}, config

    def _samples(self, params):
        queryset = Sample.objects.prefetch_related("stage_statuses")
        if params.get("batch_name_from_vendor"):
            samples = list(queryset.filter(batch_name_from_vendor=params["batch_name_from_vendor"]))
            if not samples:
                raise ValidationError(
                    f"No samples for batch {params['batch_name_from_vendor']!r}. Sync it first."
                )
            # A vendor batch can contain one half of a multiome pair. Add its partner.
            return pairing.with_multiome_partners(samples)[0]

        samples = list(queryset.filter(fastq_name__in=params["fastq_names"]))
        unknown = set(params["fastq_names"]) - {sample.fastq_name for sample in samples}
        if unknown:
            raise ValidationError(f"Unknown fastq names, sync them first: {', '.join(sorted(unknown))}")
        # Expand pairs for API requests as well as dashboard requests.
        return pairing.with_multiome_partners(samples)[0]


def _serialize_plan(plan, config: dict) -> dict:
    return {
        "entries": [
            {
                "fastq_name": entry.sample.fastq_name,
                "stage": entry.stage,
                "modality": entry.modality,
                "modality_source": entry.modality_source,
                "command": entry.command,
                "spacing": entry.spacing,
            }
            for entry in plan.entries
        ],
        "skipped": _serialize_skips(plan),
        # Report ATAC samples covered by their GEX partner's alignment command.
        "covered_by_pair": [sample.fastq_name for sample in plan.covered_by_pair],
        "modality_required": [skip.sample.fastq_name for skip in plan.needs_modality],
        "available_modalities": available_modalities(config),
    }


def _serialize_skips(plan) -> list[dict]:
    return [
        {"fastq_name": skip.sample.fastq_name, "reason": skip.reason, "detail": skip.detail}
        for skip in plan.skipped
    ]
