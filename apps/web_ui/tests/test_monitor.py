"""Job monitor and finished-stage tests."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.sample_catalog.models import Stage
from apps.submission_queue.models import QueueEntry

pytestmark = pytest.mark.django_db


class TestJobMonitor:
    def test_a_running_stage_appears(self, logged_in, make_sample):
        sample = make_sample("RUNNING-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="demand-123")

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert b"RUNNING-1" in response.content
        assert b"demand-123" in response.content
        assert response.context["counts"]["align"] == 1

    def test_fastqs_in_one_demand_collapse_with_fastq_details(self, logged_in, make_sample):
        fastq_names = [f"BATCHED-{index}" for index in range(8)]
        for fastq_name in fastq_names:
            sample = make_sample(fastq_name, batch_name_from_vendor="RFX-38026")
            sample.stage_statuses.create(
                stage=Stage.ALIGN,
                status="IN_PROGRESS",
                demand_id="one-demand",
            )

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert len(response.context["running"]) == 1
        assert response.context["counts"] == {"align": 1, "post_align": 0, "total": 1}
        assert response.context["running"][0].fastq_names == fastq_names
        assert response.context["running"][0].show_fastq_details
        assert b"View 8 fastq samples" in response.content
        assert set(response.context["monitor_fastq_names"]) == set(fastq_names)

    def test_running_and_finished_stages_show_sample_metadata(self, logged_in, make_sample):
        running = make_sample(
            "RUNNING-METADATA",
            load_name="LOAD-RUNNING",
            organism_common_name="mouse",
            library_prep_method_name="10xV4",
        )
        running.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="demand-running")
        finished = make_sample(
            "FINISHED-METADATA",
            load_name="LOAD-FINISHED",
            organism_common_name="human",
            library_prep_method_name="10xFXv2",
        )
        finished.stage_statuses.create(stage=Stage.ALIGN, status="COMPLETED", demand_id="demand-finished")

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert b"mouse" in response.content
        assert b"10xV4" in response.content
        assert b"human" in response.content
        assert b"10xFXv2" in response.content

    def test_running_stage_filter_shows_only_alignment_jobs(self, logged_in, make_sample):
        alignment = make_sample("RUNNING-ALIGN-1")
        alignment.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="demand-align")
        post_alignment = make_sample("RUNNING-POST-1")
        post_alignment.stage_statuses.create(
            stage=Stage.POST_ALIGN, status="IN_PROGRESS", demand_id="demand-post"
        )

        response = logged_in.get(reverse("web_ui:job-monitor"), {"running_stage": Stage.ALIGN})

        assert [row.sample.fastq_name for row in response.context["running"]] == ["RUNNING-ALIGN-1"]
        assert response.context["counts"] == {"align": 1, "post_align": 1, "total": 2}
        assert response.context["running_stage"] == Stage.ALIGN

    def test_running_stage_filter_shows_only_post_alignment_jobs(self, logged_in, make_sample):
        alignment = make_sample("RUNNING-ALIGN-2")
        alignment.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="demand-align-2")
        post_alignment = make_sample("RUNNING-POST-2")
        post_alignment.stage_statuses.create(
            stage=Stage.POST_ALIGN, status="IN_PROGRESS", demand_id="demand-post-2"
        )

        response = logged_in.get(reverse("web_ui:job-monitor"), {"running_stage": Stage.POST_ALIGN})

        assert [row.sample.fastq_name for row in response.context["running"]] == ["RUNNING-POST-2"]
        assert response.context["counts"] == {"align": 1, "post_align": 1, "total": 2}

    def test_invalid_running_stage_shows_all_running_jobs(self, logged_in, make_sample):
        for name, stage in (("RUNNING-ALIGN-3", Stage.ALIGN), ("RUNNING-POST-3", Stage.POST_ALIGN)):
            sample = make_sample(name)
            sample.stage_statuses.create(stage=stage, status="IN_PROGRESS", demand_id=f"demand-{name}")

        response = logged_in.get(reverse("web_ui:job-monitor"), {"running_stage": "export"})

        assert len(response.context["running"]) == 2
        assert response.context["running_stage"] == ""

    def test_finished_stage_filter_shows_only_post_alignment_jobs(self, logged_in, make_sample):
        alignment = make_sample("FINISHED-ALIGN-1")
        alignment.stage_statuses.create(stage=Stage.ALIGN, status="COMPLETED", demand_id="demand-align-fin")
        post_alignment = make_sample("FINISHED-POST-1")
        post_alignment.stage_statuses.create(
            stage=Stage.POST_ALIGN, status="COMPLETED", demand_id="demand-post-fin"
        )

        response = logged_in.get(reverse("web_ui:job-monitor"), {"finished_stage": Stage.POST_ALIGN})

        assert [row.sample.fastq_name for row in response.context["finished"]] == ["FINISHED-POST-1"]
        assert response.context["finished_stage"] == Stage.POST_ALIGN

    def test_invalid_finished_stage_shows_all_finished_jobs(self, logged_in, make_sample):
        for name, stage in (("FINISHED-ALIGN-2", Stage.ALIGN), ("FINISHED-POST-2", Stage.POST_ALIGN)):
            sample = make_sample(name)
            sample.stage_statuses.create(stage=stage, status="COMPLETED", demand_id=f"demand-{name}")

        response = logged_in.get(reverse("web_ui:job-monitor"), {"finished_stage": "export"})

        assert len(response.context["finished"]) == 2
        assert response.context["finished_stage"] == ""

    def test_finished_status_filter_shows_only_matching_jobs(self, logged_in, make_sample):
        done = make_sample("FINISHED-DONE-1")
        done.stage_statuses.create(stage=Stage.ALIGN, status="COMPLETED", demand_id="demand-done")
        failed = make_sample("FINISHED-FAILED-1")
        failed.stage_statuses.create(stage=Stage.ALIGN, status="FAILED", demand_id="demand-failed")

        response = logged_in.get(reverse("web_ui:job-monitor"), {"finished_status": "FAILED"})

        assert [row.sample.fastq_name for row in response.context["finished"]] == ["FINISHED-FAILED-1"]
        assert response.context["finished_status"] == "FAILED"

    def test_finished_status_and_stage_filters_combine(self, logged_in, make_sample):
        """Both filters narrow the same table at once, not one replacing the other."""
        align_failed = make_sample("FINISHED-ALIGN-FAILED")
        align_failed.stage_statuses.create(stage=Stage.ALIGN, status="FAILED", demand_id="demand-af")
        postalign_failed = make_sample("FINISHED-POST-FAILED")
        postalign_failed.stage_statuses.create(stage=Stage.POST_ALIGN, status="FAILED", demand_id="demand-pf")
        align_done = make_sample("FINISHED-ALIGN-DONE")
        align_done.stage_statuses.create(stage=Stage.ALIGN, status="COMPLETED", demand_id="demand-ad")

        response = logged_in.get(
            reverse("web_ui:job-monitor"), {"finished_stage": Stage.ALIGN, "finished_status": "FAILED"}
        )

        assert [row.sample.fastq_name for row in response.context["finished"]] == ["FINISHED-ALIGN-FAILED"]

    def test_invalid_finished_status_shows_all_finished_jobs(self, logged_in, make_sample):
        for name, status in (("FINISHED-A", "COMPLETED"), ("FINISHED-B", "FAILED")):
            sample = make_sample(name, load_name=f"LOAD-{name}")
            sample.stage_statuses.create(stage=Stage.ALIGN, status=status, demand_id=f"demand-{name}")

        response = logged_in.get(reverse("web_ui:job-monitor"), {"finished_status": "not-a-real-status"})

        assert len(response.context["finished"]) == 2
        assert response.context["finished_status"] == ""

    def test_finished_limit_applies_to_alignment_workflow_stages(self, logged_in, make_sample):
        make_sample("FINISHED-INGEST")
        export = make_sample("FINISHED-EXPORT")
        export.stage_statuses.create(stage=Stage.EXPORT, status="COMPLETED", demand_id="demand-export")
        for index in range(1001):
            sample = make_sample(f"FINISHED-ALIGN-{index:04d}", load_name=f"LOAD-{index}")
            sample.stage_statuses.create(
                stage=Stage.ALIGN,
                status="COMPLETED",
                demand_id=f"demand-align-{index}",
            )

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert response.context["finished"].paginator.count == 1000
        assert len(response.context["finished"]) == 50
        assert {row.stage for row in response.context["finished"]} == {Stage.ALIGN}

    def test_monitor_poll_returns_only_the_table_fragment(self, logged_in, make_sample):
        sample = make_sample("POLL-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="poll-demand")

        response = logged_in.get(reverse("web_ui:job-monitor"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        assert response.status_code == 200
        assert b"Running" in response.content
        assert b"monitor-live-data" not in response.content
        assert b"Refresh data" not in response.content

    def test_a_running_stage_shows_elapsed_duration(self, logged_in, make_sample):
        sample = make_sample("RUNNING-TIMED-1")
        sample.stage_statuses.create(
            stage=Stage.ALIGN,
            status="IN_PROGRESS",
            demand_id="demand-timed",
            started_at=timezone.now() - timedelta(minutes=5, seconds=10),
        )

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert b"5m" in response.content

    def test_monitor_tables_paginate_with_the_shared_page_size(self, logged_in, make_sample):
        for index in range(30):
            sample = make_sample(f"RUNNING-PAGE-{index:02d}", load_name=f"LOAD-{index:02d}")
            sample.stage_statuses.create(
                stage=Stage.ALIGN,
                status="IN_PROGRESS",
                demand_id=f"demand-page-{index}",
            )

        response = logged_in.get(reverse("web_ui:job-monitor"), {"running_page_size": "25"})

        assert response.context["running_page"].paginator.per_page == 25
        assert len(response.context["running_page"].object_list) == 25

    def test_a_multiome_pair_is_one_running_mtx_job(self, logged_in, make_sample):
        gex = make_sample(
            "GEX-1",
            batch_name_from_vendor="MTX-32013",
            library_prep_method_name="10xMultX_GEX",
            load_name="LOAD-PAIR",
        )
        atac = make_sample(
            "ATAC-1",
            batch_name_from_vendor="ATX-36013",
            library_prep_method_name="10xMultX_ATAC",
            load_name="LOAD-PAIR",
        )
        for sample in (atac, gex):
            sample.stage_statuses.create(
                stage=Stage.ALIGN, status="IN_PROGRESS", demand_id=f"{sample.pk}-demand"
            )

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert len(response.context["running"]) == 1
        assert response.context["running"][0].sample == gex
        assert response.context["running"][0].sample.modality == "MTX"
        assert response.context["running"][0].fastq_names == [gex.fastq_name, atac.fastq_name]
        assert not response.context["running"][0].show_fastq_details
        assert b"View 2 fastq samples" not in response.content
        assert response.context["counts"]["total"] == 1
        assert set(response.context["monitor_fastq_names"]) == {gex.fastq_name, atac.fastq_name}

    def test_running_atx_row_uses_completed_mtx_partner(self, logged_in, make_sample):
        gex = make_sample(
            "GEX-COMPLETED",
            batch_name_from_vendor="MTX-32013",
            load_name="LOAD-RUNNING-PAIR",
        )
        atac = make_sample(
            "ATAC-RUNNING",
            batch_name_from_vendor="ATX-36013",
            load_name="LOAD-RUNNING-PAIR",
        )
        gex.stage_statuses.create(stage=Stage.ALIGN, status="COMPLETED", demand_id="gex-demand")
        atac.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="atac-demand")

        response = logged_in.get(reverse("web_ui:job-monitor"))

        row = response.context["running"][0]
        assert row.sample == gex
        assert row.fastq_names == [gex.fastq_name, atac.fastq_name]
        assert response.context["counts"]["total"] == 1

    def test_a_shared_load_collapses_regardless_of_library_prep_name(self, logged_in, make_sample):
        """Collapse an MTX/ATX pair even when the prep names differ."""
        mtx = make_sample(
            "NW-MX32019-1",
            batch_name_from_vendor="MTX-32019",
            library_prep_method_name="10xRSeq_Mult",
            load_name="3698_C05",
        )
        atx = make_sample(
            "NW-AT36019-1",
            batch_name_from_vendor="ATX-36019",
            library_prep_method_name="10xATAC_Mult",
            load_name="3698_C05",
        )
        for sample in (mtx, atx):
            sample.stage_statuses.create(
                stage=Stage.ALIGN, status="IN_PROGRESS", demand_id=f"{sample.pk}-demand"
            )

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert len(response.context["running"]) == 1
        assert response.context["running"][0].sample == mtx
        assert response.context["running"][0].sample.modality == "MTX"

    def test_same_load_name_does_not_collapse_unrelated_rfx_samples(self, logged_in, make_sample):
        for name in ("RFX-1", "RFX-2"):
            sample = make_sample(name, batch_name_from_vendor="RFX-38026", load_name="SHARED-LOAD")
            sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id=f"{name}-demand")

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert {row.sample.fastq_name for row in response.context["running"]} == {"RFX-1", "RFX-2"}
        assert response.context["counts"] == {"align": 2, "post_align": 0, "total": 2}

    def test_a_demand_submitted_outside_omicshub_is_shown_and_labelled(self, logged_in, make_sample):
        """The whole point: no queue entry holds this demand id, and it still appears."""
        sample = make_sample("EXTERNAL-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="not-ours")

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert b"EXTERNAL-1" in response.content
        assert not response.context["running"][0].queued_here
        assert b"External" in response.content

    def test_a_demand_this_app_queued_is_labelled_as_such(self, logged_in, queued):
        entry = queued("OURS-1")
        entry.status = QueueEntry.Status.SUBMITTED
        entry.demand_id = "demand-ours"
        entry.save()
        entry.sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="demand-ours")

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert response.context["running"][0].queued_here
        assert b"OmicsHub" in response.content

    def test_a_finished_stage_moves_to_the_finished_table(self, logged_in, make_sample):
        sample = make_sample("DONE-1")
        sample.stage_statuses.create(
            stage=Stage.ALIGN, status="COMPLETED", demand_id="demand-done", duration_seconds=10080
        )

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert not response.context["running"]
        assert [row.sample.fastq_name for row in response.context["finished"]] == ["DONE-1"]
        assert b"2h 48m" in response.content

    def test_a_failed_stage_is_finished_rather_than_running(self, logged_in, make_sample):
        """FAILED and ABORTED are outcomes. Left out of both tables they vanish entirely."""
        sample = make_sample("FAILED-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="FAILED", demand_id="demand-bad")

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert [row.status for row in response.context["finished"]] == ["FAILED"]

    def test_a_stage_ocs_has_never_run_is_not_a_job(self, logged_in, make_sample):
        """`make_sample` writes an ingest row with a demand id and nothing else; a stage
        with no demand is a row the sweep created, not work anyone submitted."""
        sample = make_sample("IDLE-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="NOT COMPLETED", demand_id="")

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert not response.context["running"]
        assert "ALIGN" not in [row.stage for row in response.context["finished"]]

    def test_another_users_submissions_are_visible(self, logged_in, make_sample, django_user_model):
        """Unlike the queue, this page is the pipeline, not a personal list."""
        other = django_user_model.objects.create_user(username="colleague")
        sample = make_sample("THEIRS-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="demand-theirs")
        QueueEntry.objects.create(
            sample=sample,
            stage=Stage.ALIGN,
            requested_by=other,
            modality="MTX",
            modality_source=QueueEntry.ModalitySource.INFERRED,
            notify_email="colleague@example.org",
            command_args=["ocs"],
            command="ocs",
            spacing=180,
            status=QueueEntry.Status.SUBMITTED,
            demand_id="demand-theirs",
        )

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert b"THEIRS-1" in response.content

    def test_the_row_count_does_not_grow_with_the_number_of_jobs(
        self, logged_in, make_sample, django_assert_num_queries
    ):
        """Use bounded queries for the monitor tables, freshness label, and failure badge."""
        for index in range(6):
            sample = make_sample(f"MANY-{index}")
            sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id=f"demand-{index}")
        logged_in.get(reverse("web_ui:job-monitor"))

        with django_assert_num_queries(9):
            logged_in.get(reverse("web_ui:job-monitor"))
