"""Job timeline tests."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.sample_catalog.models import Stage

pytestmark = pytest.mark.django_db


class TestJobTimeline:
    def test_status_filter_offers_three_workflow_statuses(self, logged_in):
        response = logged_in.get(reverse("web_ui:job-timeline"))

        assert response.context["status_options"] == (
            {"value": "IN_PROGRESS", "label": "In progress"},
            {"value": "FAILED", "label": "Failed"},
            {"value": "COMPLETED", "label": "Completed"},
        )

    def test_uses_the_stage_timestamp_and_duration(self, logged_in, make_sample):
        started_at = timezone.now() - timedelta(hours=2)
        sample = make_sample("TIMELINE-1", batch_name_from_vendor="MTX-22068")
        sample.stage_statuses.create(
            stage=Stage.ALIGN,
            status="COMPLETED",
            demand_id="demand-123",
            started_at=started_at,
            duration_seconds=3600,
        )

        response = logged_in.get(
            reverse("web_ui:job-timeline"),
            {"date": timezone.localdate().isoformat()},
        )

        row = response.context["timeline_rows"][0]
        assert row["fastq_names"] == ["TIMELINE-1"]
        assert row["bars"][0]["duration"] == "1h"

    def test_month_view_shows_sample_and_stage_counts(self, logged_in, make_sample):
        started_at = timezone.now() - timedelta(hours=2)
        sample = make_sample("TIMELINE-MONTH-1", batch_name_from_vendor="MTX-22068")
        sample.stage_statuses.create(
            stage=Stage.ALIGN,
            status="COMPLETED",
            started_at=started_at,
            duration_seconds=3600,
        )
        sample.stage_statuses.create(
            stage=Stage.POST_ALIGN,
            status="FAILED",
            started_at=started_at,
            duration_seconds=600,
        )

        response = logged_in.get(
            reverse("web_ui:job-timeline"),
            {
                "view": "month",
                "date": timezone.localdate().isoformat(),
                "day": timezone.localdate().isoformat(),
            },
        )

        today = next(
            cell
            for cell in response.context["timeline_periods"]["cells"]
            if cell and cell["date"] == timezone.localdate()
        )
        assert today["fastq_samples"] == 1
        assert today["batch_names"] == 1
        assert today["batches"] == (
            {
                "name": "MTX-22068",
                "fastq_samples": (
                    {
                        "name": "TIMELINE-MONTH-1",
                        "stages": (
                            {
                                "label": "A",
                                "stage": "Alignment",
                                "status": "Completed",
                                "status_class": "completed",
                            },
                            {
                                "label": "P",
                                "stage": "Post-Alignment",
                                "status": "Failed",
                                "status_class": "failed",
                            },
                        ),
                    },
                ),
            },
        )
        assert today["status_items"][0]["label"] == "Alignment"
        stages = {stage["label"]: stage for stage in today["stages"]}
        assert stages["Alignment"]["completed_stages"] == 1
        assert stages["Post-Alignment"]["failed_stages"] == 1

    def test_year_view_has_one_card_per_month(self, logged_in):
        response = logged_in.get(
            reverse("web_ui:job-timeline"),
            {"view": "year", "date": timezone.localdate().isoformat()},
        )

        assert len(response.context["timeline_periods"]["months"]) == 12
