"""Job timeline tests."""

from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.sample_catalog.models import Sample, Stage

pytestmark = pytest.mark.django_db


class TestJobTimeline:
    def test_status_filter_offers_direct_ocs_statuses(self, logged_in):
        response = logged_in.get(reverse("web_ui:job-timeline"))

        assert response.context["status_options"] == (
            {"value": "IN_PROGRESS", "label": "IN_PROGRESS"},
            {"value": "FAILED", "label": "FAILED"},
            {"value": "COMPLETED", "label": "COMPLETED"},
            {"value": "ABORTED", "label": "ABORTED"},
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
        started_at = timezone.make_aware(datetime.combine(timezone.localdate(), time(hour=12)))
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
                        "fastq_names": ("TIMELINE-MONTH-1",),
                        "show_fastq_details": True,
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

    def test_month_day_detail_uses_monitor_sample_grouping(self, logged_in, make_sample):
        started_at = timezone.make_aware(datetime.combine(timezone.localdate(), time(hour=12)))
        make_sample("NY-MX22096-1", batch_name_from_vendor="MTX-22096", load_name="LOAD-1")
        make_sample("NY-AT26096-1", batch_name_from_vendor="ATX-26096", load_name="LOAD-1")
        make_sample("RFX-PAIR-1", batch_name_from_vendor="RFX-38025", load_name="LOAD-2")
        make_sample("RFX-1", batch_name_from_vendor="RFX-38026")
        make_sample("RFX-2", batch_name_from_vendor="RFX-38026")
        Sample.objects.get(fastq_name="NY-MX22096-1").stage_statuses.create(
            stage=Stage.POST_ALIGN,
            status="COMPLETED",
            demand_id="pair-demand",
            started_at=started_at,
            duration_seconds=3600,
        )
        Sample.objects.get(fastq_name="NY-AT26096-1").stage_statuses.create(
            stage=Stage.POST_ALIGN,
            status="COMPLETED",
            demand_id="pair-demand",
            started_at=started_at,
            duration_seconds=3600,
        )
        Sample.objects.get(fastq_name="RFX-PAIR-1").stage_statuses.create(
            stage=Stage.POST_ALIGN,
            status="COMPLETED",
            demand_id="pair-demand",
            started_at=started_at,
            duration_seconds=3600,
        )
        for fastq_name in ("RFX-1", "RFX-2"):
            Sample.objects.get(fastq_name=fastq_name).stage_statuses.create(
                stage=Stage.POST_ALIGN,
                status="COMPLETED",
                demand_id="shared-demand",
                started_at=started_at,
                duration_seconds=3600,
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
        assert today["fastq_samples"] == 2
        assert today["batch_names"] == 2
        assert [batch["name"] for batch in today["batches"]] == [
            "MTX-22096",
            "RFX-38026",
        ]
        grouped_pair = today["batches"][0]["fastq_samples"][0]
        assert grouped_pair["name"] == "NY-MX22096-1 + 2 more"
        assert grouped_pair["fastq_names"] == (
            "NY-MX22096-1",
            "NY-AT26096-1",
            "RFX-PAIR-1",
        )
        assert grouped_pair["stages"][0]["label"] == "P"

        grouped_demand = today["batches"][1]["fastq_samples"][0]
        assert grouped_demand["name"] == "RFX-1 + 1 more"
        assert grouped_demand["fastq_names"] == ("RFX-1", "RFX-2")

    def test_year_view_has_one_card_per_month(self, logged_in):
        response = logged_in.get(
            reverse("web_ui:job-timeline"),
            {"view": "year", "date": timezone.localdate().isoformat()},
        )

        assert len(response.context["timeline_periods"]["months"]) == 12
