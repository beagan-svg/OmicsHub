"""Render timeline pages and actions."""

import calendar
from datetime import date, datetime, timedelta
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncDay, TruncMonth
from django.shortcuts import render
from django.utils import timezone

from apps.sample_catalog.models import BatchPrefix, Sample, Stage, StageStatus

from .common import FINISHED_OCS_STATUSES, RUNNING_OCS_STATUSES, TIMELINE_DAYS, TIMELINE_PAGE_SIZE
from .monitor import _collapse_multiome_monitor_rows

TIMELINE_STATUS_GROUPS = {
    "IN_PROGRESS": RUNNING_OCS_STATUSES,
    "FAILED": ("FAILED", "ABORTED", "STRANDED", "ABANDONED"),
    "COMPLETED": ("COMPLETED", "ARCHIVED"),
}
TIMELINE_STAGE_LABELS = {
    Stage.ALIGN: "Alignment",
    Stage.POST_ALIGN: "Post-Alignment",
}


@login_required
def job_timeline(request):
    """Show grouped workflow stages for a selected calendar range."""
    now = timezone.now()
    selected_view = request.GET.get("view", "week")
    if selected_view not in {"week", "month", "year"}:
        selected_view = "week"
    selected_date = _timeline_date(request.GET.get("date"), now)
    selected_day = None
    if selected_view == "month" and request.GET.get("day"):
        candidate_day = _timeline_date(request.GET.get("day"), now)
        if candidate_day.month == selected_date.month and candidate_day.year == selected_date.year:
            selected_day = candidate_day
    context: dict[str, Any]
    if selected_view == "week":
        week_start = selected_date - timedelta(days=selected_date.weekday())
        window_start = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
        window_end = window_start + timedelta(days=7)
    elif selected_view == "month":
        window_start = timezone.make_aware(datetime(selected_date.year, selected_date.month, 1))
        window_end = (window_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        window_start = timezone.make_aware(datetime(selected_date.year, 1, 1))
        window_end = timezone.make_aware(datetime(selected_date.year + 1, 1, 1))

    selected_stage = request.GET.get("stage", "")
    if selected_stage not in {Stage.ALIGN.value, Stage.POST_ALIGN.value}:
        selected_stage = ""
    selected_status = request.GET.get("status", "")
    if selected_status not in TIMELINE_STATUS_GROUPS:
        selected_status = ""

    stages = StageStatus.objects.select_related("sample")
    stages = stages.filter(stage__in=(Stage.ALIGN, Stage.POST_ALIGN), started_at__isnull=False)
    stages = stages.filter(
        Q(started_at__lt=window_end)
        & (
            Q(started_at__gte=window_start)
            | Q(last_update_time__gte=window_start)
            | Q(status__in=RUNNING_OCS_STATUSES)
        )
    )
    if selected_stage:
        stages = stages.filter(stage=selected_stage)
    if selected_status:
        stages = stages.filter(status__in=TIMELINE_STATUS_GROUPS[selected_status])

    if selected_view == "week":
        batch_rows: dict[str, dict[str, list[StageStatus]]] = {}
        stage_rows = list(stages.order_by("started_at"))
        load_names = {
            stage_status.sample.load_name for stage_status in stage_rows if stage_status.sample.load_name
        }
        mtx_batches: dict[str, str] = {}
        for load_name, batch_name in (
            Sample.objects.filter(load_name__in=load_names, batch_prefix=BatchPrefix.MTX)
            .order_by("batch_name_from_vendor")
            .values_list("load_name", "batch_name_from_vendor")
        ):
            mtx_batches.setdefault(load_name, batch_name)
        for stage_status in stage_rows:
            sample = stage_status.sample
            batch_name = sample.batch_name_from_vendor or "Unassigned batch"
            if sample.batch_prefix == BatchPrefix.ATX:
                batch_name = mtx_batches.get(sample.load_name, batch_name)
            load_name = sample.load_name or sample.fastq_name
            batch_rows.setdefault(batch_name, {}).setdefault(load_name, []).append(stage_status)

        timeline_groups: list[dict[str, Any]] = [
            {
                "batch": batch_name,
                "fastq_count": len(
                    {stage.sample.fastq_name for rows in load_groups.values() for stage in rows}
                ),
                "rows": [
                    _timeline_sample_row(
                        sorted({stage.sample.fastq_name for stage in loads}),
                        _collapse_timeline_stages(loads),
                        window_start,
                        window_end,
                        now,
                    )
                    for loads in load_groups.values()
                ],
            }
            for batch_name, load_groups in batch_rows.items()
        ]
        page = Paginator(timeline_groups, TIMELINE_PAGE_SIZE).get_page(request.GET.get("page"))
        context = {
            "timeline_page": page,
            "timeline_groups": page.object_list,
            "timeline_rows": [row for group in page.object_list for row in group["rows"]],
            "timeline_days": [
                window_start.date() + timedelta(days=offset) for offset in range(TIMELINE_DAYS)
            ],
        }
    else:
        periods = _timeline_periods(stages, selected_view, selected_date, selected_day)
        context = {
            "timeline_page": None,
            "timeline_rows": [],
            "timeline_periods": periods,
        }

    return render(
        request,
        "job_timeline.html",
        {
            **context,
            "selected_view": selected_view,
            "view_options": ("week", "month", "year"),
            "selected_date": selected_date,
            "selected_day": selected_day,
            "period_label": _timeline_period_label(selected_view, selected_date),
            "previous_date": _timeline_shift_date(selected_view, selected_date, -1),
            "next_date": _timeline_shift_date(selected_view, selected_date, 1),
            "window_start": window_start,
            "window_end": window_end,
            "selected_stage": selected_stage,
            "selected_status": selected_status,
            "stage_options": (Stage.ALIGN, Stage.POST_ALIGN),
            "status_options": (
                {"value": "IN_PROGRESS", "label": "In progress"},
                {"value": "FAILED", "label": "Failed"},
                {"value": "COMPLETED", "label": "Completed"},
            ),
        },
    )


def _timeline_date(value, now):
    if not value:
        return timezone.localdate(now)
    try:
        return date.fromisoformat(value)
    except ValueError:
        return timezone.localdate(now)


def _timeline_shift_date(selected_view, selected_date, direction):
    if selected_view == "week":
        return selected_date + timedelta(days=7 * direction)
    if selected_view == "month":
        month = selected_date.month - 1 + direction
        year, month = divmod(month, 12)
        return date(selected_date.year + year, month + 1, 1)
    return date(selected_date.year + direction, 1, 1)


def _timeline_period_label(selected_view, selected_date):
    if selected_view == "week":
        start = selected_date - timedelta(days=selected_date.weekday())
        return f"{start:%b %-d} – {(start + timedelta(days=6)):%b %-d, %Y}"
    if selected_view == "month":
        return selected_date.strftime("%B %Y")
    return str(selected_date.year)


def _timeline_periods(stages, selected_view, selected_date, selected_day=None):
    """Build status counts for each day in a month or month in a year."""
    truncation = TruncDay if selected_view == "month" else TruncMonth
    aggregate_rows = (
        stages.annotate(period=truncation("started_at"))
        .values("period", "stage")
        .annotate(
            total_stages=Count("pk"),
            fastq_samples=Count("sample_id", distinct=True),
            completed_stages=Count("pk", filter=Q(status__in=TIMELINE_STATUS_GROUPS["COMPLETED"])),
            failed_stages=Count("pk", filter=Q(status__in=TIMELINE_STATUS_GROUPS["FAILED"])),
            running_stages=Count("pk", filter=Q(status__in=TIMELINE_STATUS_GROUPS["IN_PROGRESS"])),
        )
        .order_by("period", "stage")
    )
    sample_counts = {
        row["period"].date(): row["fastq_samples"]
        for row in stages.annotate(period=truncation("started_at"))
        .values("period")
        .annotate(fastq_samples=Count("sample_id", distinct=True))
    }
    batch_counts = {
        row["period"].date(): row["batch_names"]
        for row in stages.annotate(period=truncation("started_at"))
        .values("period")
        .annotate(
            batch_names=Count(
                "sample__batch_name_from_vendor",
                distinct=True,
                filter=~Q(sample__batch_name_from_vendor=""),
            )
        )
    }
    by_period: dict[date, dict[str, Any]] = {}
    for row in aggregate_rows:
        period = row["period"].date()
        period_data = by_period.setdefault(
            period,
            {"stages": {}},
        )
        period_data["stages"][row["stage"]] = row

    selected_day_batches = _timeline_day_batches(stages, selected_day) if selected_day else ()

    if selected_view == "month":
        month_start = selected_date.replace(day=1)
        days_in_month = calendar.monthrange(selected_date.year, selected_date.month)[1]
        cells = [None] * month_start.weekday()
        cells.extend(
            _period_card_data(
                month_start + timedelta(days=offset),
                by_period,
                sample_counts,
                batch_counts,
                selected_day_batches if month_start + timedelta(days=offset) == selected_day else (),
            )
            for offset in range(days_in_month)
        )
        cells.extend([None] * ((-len(cells)) % 7))
        return {"kind": "month", "cells": cells}

    months = []
    for month in range(1, 13):
        month_date = date(selected_date.year, month, 1)
        months.append(_period_card_data(month_date, by_period, sample_counts, batch_counts))
    return {"kind": "year", "months": months}


def _period_card_data(period, by_period, sample_counts, batch_counts, batches=()):
    """Return display counts for one calendar period."""
    period_data = by_period.get(period, {"stages": {}})
    stage_counts = period_data["stages"]
    return {
        "date": period,
        "fastq_samples": sample_counts.get(period, 0),
        "batch_names": batch_counts.get(period, 0),
        "batches": batches,
        "status_summary": _period_status_summary(stage_counts),
        "stages": [
            {
                "label": TIMELINE_STAGE_LABELS[stage],
                **stage_counts.get(
                    stage,
                    {
                        "total_stages": 0,
                        "completed_stages": 0,
                        "failed_stages": 0,
                        "running_stages": 0,
                    },
                ),
            }
            for stage in (Stage.ALIGN, Stage.POST_ALIGN)
        ],
        "status_items": _period_status_items(stage_counts),
    }


def _timeline_day_batches(stages, selected_day):
    """Return Batch Name From Vendor groups and Fastq Samples for one day."""
    rows = (
        stages.filter(started_at__date=selected_day)
        .values_list(
            "sample__batch_name_from_vendor",
            "sample__fastq_name",
            "stage",
            "status",
        )
        .distinct()
        .order_by("sample__batch_name_from_vendor", "sample__fastq_name", "stage")
    )
    batches: dict[str, Any] = {}
    for batch_name, fastq_name, stage, status in rows:
        batch = batches.setdefault(batch_name or "Unassigned batch", {})
        sample = batch.setdefault(fastq_name, {})
        sample[stage] = {
            "label": "A" if stage == Stage.ALIGN else "P",
            "stage": TIMELINE_STAGE_LABELS[Stage(stage)],
            "status": status.replace("_", " ").capitalize(),
            "status_class": status.lower().replace("_", "-"),
        }
    return tuple(
        {
            "name": batch_name,
            "fastq_samples": tuple(
                {
                    "name": fastq_name,
                    "stages": tuple(sample.values()),
                }
                for fastq_name, sample in fastq_names.items()
            ),
        }
        for batch_name, fastq_names in batches.items()
    )


def _period_status_items(stage_counts):
    """Return nonzero stage outcomes for a calendar period."""
    stage_short_labels = {
        Stage.ALIGN: "A",
        Stage.POST_ALIGN: "P",
    }
    status_counts = (
        ("completed_stages", "completed", "Completed"),
        ("failed_stages", "failed", "Failed"),
        ("running_stages", "running", "Running"),
    )
    items = []
    for stage in (Stage.ALIGN, Stage.POST_ALIGN):
        counts = stage_counts.get(stage)
        if not counts:
            continue
        for field, status, status_label in status_counts:
            count = counts[field]
            if count:
                items.append(
                    {
                        "short_label": stage_short_labels[stage],
                        "label": TIMELINE_STAGE_LABELS[stage],
                        "count": count,
                        "status": status,
                        "status_label": status_label,
                    }
                )
    return items


def _period_status_summary(stage_counts):
    summary: dict[str, list[dict[str, Any]]] = {}
    for item in _period_status_items(stage_counts):
        summary.setdefault(item["label"], []).append(item)
    return tuple({"label": label, "items": tuple(items)} for label, items in summary.items())


def _timeline_sample_row(fastq_names, stages, window_start, window_end, now):
    bars = [_timeline_bar(stage_status, window_start, window_end, now) for stage_status in stages]
    return {
        "sample": fastq_names[0],
        "fastq_names": fastq_names,
        "fastq_pair": (
            " & ".join(sorted(fastq_names, key=lambda name: "-MX" not in name))
            if len(fastq_names) == 2
            else ""
        ),
        "bars": bars,
    }


def _collapse_timeline_stages(stages):
    running = [stage for stage in stages if stage.status in RUNNING_OCS_STATUSES]
    finished = [stage for stage in stages if stage.status in FINISHED_OCS_STATUSES]
    collapsed_running, collapsed_finished = _collapse_multiome_monitor_rows(
        running, finished, include_queue_status=False
    )
    return [row.stage_status for row in [*collapsed_running, *collapsed_finished]]


def _timeline_bar(stage_status, window_start, window_end, now):
    started_at = max(stage_status.started_at, window_start)
    if stage_status.status in RUNNING_OCS_STATUSES:
        finished_at = now
    elif stage_status.duration_seconds is not None:
        finished_at = stage_status.started_at + timedelta(seconds=stage_status.duration_seconds)
    else:
        finished_at = stage_status.last_update_time or stage_status.started_at
    finished_at = min(max(finished_at, started_at), window_end, now)
    total_seconds = (window_end - window_start).total_seconds()
    return {
        "stage": TIMELINE_STAGE_LABELS[stage_status.stage],
        "stage_class": stage_status.stage,
        "status": stage_status.status,
        "status_class": stage_status.status.lower().replace("_", "-"),
        "duration": stage_status.duration_display_at(finished_at),
        "left": max(0, (started_at - window_start).total_seconds() / total_seconds * 100),
        "width": max(0.25, (finished_at - started_at).total_seconds() / total_seconds * 100),
    }
