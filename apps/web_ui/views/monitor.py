"""Render monitor pages and actions."""

from collections.abc import Sequence

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Exists, F, OuterRef, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.ocs_integration import log_credentials
from apps.sample_catalog.models import MULTIOME_PREFIXES, BatchPrefix, Stage, StageStatus
from apps.submission_queue.models import QueueEntry

from .common import (
    FAILED_STATUSES,
    FINISHED_OCS_STATUSES,
    MONITOR_ROWS,
    PAGE_SIZE_OPTIONS,
    QUEUED_STATUSES,
    RUNNING_OCS_STATUSES,
    _owned,
    _page_size,
    _status_sync_context,
)

_MONITOR_STAGE_OPTIONS = [("", "All"), (Stage.ALIGN, "Alignment"), (Stage.POST_ALIGN, "Post-Alignment")]
_MONITOR_FINISHED_STATUS_OPTIONS = [
    ("", "All"),
    ("COMPLETED", "Completed"),
    ("FAILED", "Failed"),
    ("ABORTED", "Aborted"),
]


def job_monitor(request):
    """Show OCS stages that are running or finished."""
    submitted_here = QueueEntry.objects.filter(demand_id=OuterRef("demand_id")).exclude(demand_id="")
    running_stage = request.GET.get("running_stage")
    if running_stage not in {Stage.ALIGN, Stage.POST_ALIGN}:
        running_stage = ""
    finished_stage = request.GET.get("finished_stage")
    if finished_stage not in {Stage.ALIGN, Stage.POST_ALIGN}:
        finished_stage = ""
    finished_status = request.GET.get("finished_status")
    if finished_status not in FINISHED_OCS_STATUSES:
        finished_status = ""

    stages = (
        StageStatus.objects.select_related("sample")
        .exclude(demand_id="")
        .annotate(queued_here=Exists(submitted_here))
    )

    running_stages = stages.filter(status__in=RUNNING_OCS_STATUSES)
    # OCS limits the number of running stages. Finished stages use a separate display cap.
    running_rows = list(running_stages.order_by(F("started_at").desc(nulls_last=True)))
    finished = list(_finished_stages_queryset(stages, finished_stage, finished_status))
    all_monitor_running, monitor_finished = _collapse_multiome_monitor_rows(running_rows, finished)
    monitor_running = [
        row for row in all_monitor_running if not running_stage or row.stage == running_stage
    ]
    monitor_fastq_names = list(dict.fromkeys(row.sample.fastq_name for row in [*monitor_running, *finished]))
    running_page_size = _page_size(request, "running_page_size")
    finished_page_size = _page_size(request, "finished_page_size")
    running_page = Paginator(monitor_running, running_page_size).get_page(request.GET.get("running_page"))
    finished_page = Paginator(monitor_finished, finished_page_size).get_page(request.GET.get("finished_page"))

    context = {
        "running": running_page,
        "finished": finished_page,
        "running_page": running_page,
        "finished_page": finished_page,
        "running_page_size": running_page_size,
        "finished_page_size": finished_page_size,
        "page_size_options": PAGE_SIZE_OPTIONS,
        "monitor_fastq_names": monitor_fastq_names,
        "row_limit": MONITOR_ROWS,
        "running_stage": running_stage,
        "running_stage_options": _monitor_filter_options(
            request, options=_MONITOR_STAGE_OPTIONS, param="running_stage", page_param="running_page"
        ),
        "finished_stage": finished_stage,
        "finished_stage_options": _monitor_filter_options(
            request, options=_MONITOR_STAGE_OPTIONS, param="finished_stage", page_param="finished_page"
        ),
        "finished_status": finished_status,
        "finished_status_options": _monitor_filter_options(
            request,
            options=_MONITOR_FINISHED_STATUS_OPTIONS,
            param="finished_status",
            page_param="finished_page",
        ),
        "counts": {
            "align": sum(1 for row in all_monitor_running if row.stage == Stage.ALIGN),
            "post_align": sum(1 for row in all_monitor_running if row.stage == Stage.POST_ALIGN),
            "total": len(all_monitor_running),
        },
        **_status_sync_context(),
        # The queue is this app's own, so these two stay scoped to the reader.
        **_owned(request).aggregate(
            queued=Count("pk", filter=Q(status__in=QUEUED_STATUSES)),
            failed=Count("pk", filter=Q(status__in=FAILED_STATUSES)),
        ),
    }
    template = (
        "partials/job_monitor_tables.html"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest"
        else "job_monitor.html"
    )
    return render(request, template, context)


def _finished_stages_queryset(stages, finished_stage, finished_status):
    """Return the newest finished alignment and post-alignment stages up to the display limit."""
    finished_stages = stages.filter(
        stage__in=(Stage.ALIGN, Stage.POST_ALIGN),
        status__in=FINISHED_OCS_STATUSES,
    )
    if finished_stage:
        finished_stages = finished_stages.filter(stage=finished_stage)
    if finished_status:
        finished_stages = finished_stages.filter(status=finished_status)
    return finished_stages.order_by(F("last_update_time").desc(nulls_last=True))[:MONITOR_ROWS]


def _monitor_demand_is_visible(request, demand_id: str) -> bool:
    """Return whether the log viewer may fetch this demand's logs."""
    stages = StageStatus.objects.exclude(demand_id="")
    if stages.filter(demand_id=demand_id, status__in=RUNNING_OCS_STATUSES).exists():
        return True

    recent_finished_ids = _finished_stages_queryset(stages, "", "").values("pk")
    if stages.filter(pk__in=Subquery(recent_finished_ids), demand_id=demand_id).exists():
        return True

    return (
        _owned(request)
        .filter(
            demand_id=demand_id,
            status=QueueEntry.Status.FAILED,
        )
        .exists()
    )


def job_credentials_submit(request):
    """Validate temporary AWS credentials and cache them for this session."""
    access_key = request.POST.get("access_key", "").strip()
    secret_key = request.POST.get("secret_key", "").strip()
    session_token = request.POST.get("session_token", "").strip()
    try:
        identity = log_credentials.validate_credentials(request, access_key, secret_key, session_token)
    except log_credentials.CredentialError as exc:
        return JsonResponse({"status": "invalid", "code": exc.code, "message": str(exc)}, status=400)
    return JsonResponse({"status": "valid", "account": identity.account, "arn": identity.arn})


def job_credentials_clear(request):
    """Drop this session's cached credentials, if any."""
    log_credentials.clear_credentials(request)
    return JsonResponse({"status": "cleared"})


def job_credentials_status(request):
    """Return the cached credential status without making an AWS request."""
    identity = log_credentials.get_identity(request)
    if identity is None:
        return JsonResponse({"status": "required"})
    return JsonResponse({"status": "valid", "account": identity.account, "arn": identity.arn})


def job_demand_logs(request, demand_id):
    """Return recent container log lines for one demand, using this session's credentials.

    Only a demand id currently visible on the Monitor page (running, recently finished,
    or failed) can be looked up -- this is checked before the cached credentials are
    ever used for anything, so the log viewer cannot become a general AWS Batch/Logs
    lookup for arbitrary demand ids.
    """
    if not _monitor_demand_is_visible(request, demand_id):
        return JsonResponse({"status": "not_visible"}, status=403)
    stage = request.GET.get("stage")
    if stage not in {Stage.ALIGN.value, Stage.POST_ALIGN.value}:
        return JsonResponse({"status": "invalid_stage"}, status=400)
    stage_status = (
        StageStatus.objects.filter(demand_id=demand_id, stage=stage).values("status", "execution_arn").first()
    )
    execution_arn = stage_status["execution_arn"] if stage_status else ""
    failed = (stage_status and stage_status["status"] == "FAILED") or QueueEntry.objects.filter(
        demand_id=demand_id, stage=stage, status=QueueEntry.Status.FAILED
    ).exists()
    if not failed and not execution_arn:
        return JsonResponse(
            {
                "status": "aws_error",
                "code": "MissingExecutionArn",
                "message": "This demand has no stored execution record yet.",
            },
            status=502,
        )
    try:
        events = log_credentials.fetch_job_logs(request, demand_id, execution_arn, stage=stage, failed=failed)
    except log_credentials.NoCredentials:
        return JsonResponse({"status": "no_credentials"}, status=401)
    except log_credentials.CredentialError as exc:
        status = 401 if exc.rejected else 502
        return JsonResponse({"status": "aws_error", "code": exc.code, "message": str(exc)}, status=status)
    return JsonResponse({"status": "ok", "events": events})


def _monitor_filter_options(request, *, options, param, page_param):
    """Build one monitor table filter's query-string links.

    Shared by the stage and finished-status filters. Both provide an empty `All` option and
    a fixed list of values.
    """
    result = []
    for value, label in options:
        query = request.GET.copy()
        query.pop(page_param, None)
        if value:
            query[param] = value
        else:
            query.pop(param, None)
        result.append({"label": label, "value": value, "url": f"?{query.urlencode()}"})
    return result


def _collapse_multiome_monitor_rows(
    running: Sequence[StageStatus], finished: Sequence[StageStatus]
) -> tuple[list[StageStatus], list[StageStatus]]:
    """Represent each MTX/ATX pair as one MTX monitor row."""
    rows = [*running, *finished]
    prefixes_by_stage_and_load: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        if row.sample.load_name and row.sample.batch_prefix in MULTIOME_PREFIXES:
            key = (row.stage, row.sample.load_name)
            prefixes_by_stage_and_load.setdefault(key, set()).add(row.sample.batch_prefix)

    multiome_keys = {
        key for key, prefixes in prefixes_by_stage_and_load.items() if set(MULTIOME_PREFIXES) <= prefixes
    }
    selected: dict[tuple[str, str | int], StageStatus] = {}
    order: list[tuple[str, str | int]] = []

    for row in rows:
        sample = row.sample
        key = (
            (row.stage, sample.load_name)
            if (row.stage, sample.load_name) in multiome_keys
            else ("sample", row.pk)
        )
        current = selected.get(key)
        if current is None:
            selected[key] = row
            order.append(key)
            continue

        current_is_running = current.status in RUNNING_OCS_STATUSES
        row_is_running = row.status in RUNNING_OCS_STATUSES
        current_is_mtx = current.sample.batch_prefix == BatchPrefix.MTX
        row_is_mtx = sample.batch_prefix == BatchPrefix.MTX
        if (row_is_running and not current_is_running) or (
            row_is_running == current_is_running and row_is_mtx and not current_is_mtx
        ):
            selected[key] = row

    collapsed = [selected[key] for key in order]
    return (
        [row for row in collapsed if row.status in RUNNING_OCS_STATUSES],
        [row for row in collapsed if row.status in FINISHED_OCS_STATUSES],
    )


def failed_jobs(request):
    owned = _owned(request).select_related("sample", "requested_by")
    entries = owned.filter(status__in=FAILED_STATUSES, demand_id="")
    running_failures = owned.filter(status=QueueEntry.Status.FAILED).exclude(demand_id="")
    entries = list(entries)
    running_failures = list(running_failures)
    for entry in [*entries, *running_failures]:
        entry.can_retry = True
    return render(
        request,
        "failed_jobs.html",
        {
            "entries": entries,
            "running_failures": running_failures,
            "failure_count": len(entries) + len(running_failures),
        },
    )


def retry_job(request, pk):
    """Return a retryable failed job to the pending queue."""
    entry = get_object_or_404(_owned(request), pk=pk)
    # Conditional on FAILED for the same reason `cancel` is conditional on PENDING: the
    # worker may claim the entry between reading it and writing it back.
    if QueueEntry.objects.filter(
        pk=entry.pk,
        status=QueueEntry.Status.FAILED,
    ).update(
        status=QueueEntry.Status.PENDING,
        demand_id="",
        submitted_at=None,
        error_message="",
    ):
        messages.success(request, f"{entry.sample.fastq_name} is back on the queue.")
    else:
        messages.error(request, f"{entry.sample.fastq_name} is {entry.status} and cannot be retried.")
    return redirect("web_ui:failed")


def delete_job(request, pk):
    entry = get_object_or_404(_owned(request), pk=pk)
    if entry.status not in FAILED_STATUSES:
        messages.error(request, "Only failed entries can be deleted.")
    else:
        fastq_name = entry.sample.fastq_name
        entry.delete()
        messages.success(request, f"Deleted the failed entry for {fastq_name}.")
    return redirect("web_ui:failed")
