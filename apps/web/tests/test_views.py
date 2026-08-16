"""The pages, and the three-step submission the dashboard exists for."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.catalog.models import NOT_COMPLETED, Stage
from apps.queueing.models import QueueEntry
from apps.web import columns

pytestmark = pytest.mark.django_db


@pytest.fixture
def queued(logged_in, active_config, make_sample):
    """Run the whole submission flow and return the resulting entry."""

    def _queue(fastq_name="READY-1", **sample_kwargs):
        make_sample(fastq_name, **sample_kwargs)
        logged_in.post(reverse("web:submit-confirm"), {"fastq_names": [fastq_name]})
        return QueueEntry.objects.get(sample__fastq_name=fastq_name)

    return _queue


class TestAccess:
    @pytest.mark.parametrize(
        "name", ["web:dashboard", "web:queue", "web:job-monitor", "web:failed", "web:configs"]
    )
    def test_pages_require_login(self, client, name):
        response = client.get(reverse(name))

        assert response.status_code == 302
        assert "/accounts/login/" in response["Location"]

    def test_config_page_is_staff_only(self, logged_in):
        """403, not a redirect to the sign-in form.

        `user_passes_test` used to bounce a signed-in non-staff user to LOGIN_URL, so the
        page looked like it had logged them out , they signed in again and were bounced
        again, with nothing ever saying they lacked access.
        """
        assert logged_in.get(reverse("web:configs")).status_code == 403


class TestDashboard:
    def test_lists_samples_with_stage_status(self, logged_in, make_sample):
        make_sample("READY-1", align="IN_PROGRESS")

        response = logged_in.get(reverse("web:dashboard"))

        assert b"READY-1" in response.content
        assert b"IN_PROGRESS" in response.content

    def test_shows_the_inferred_workflow(self, logged_in, active_config, make_sample):
        make_sample("READY-1", batch_name_from_vendor="MTX-22068")

        assert b"MTX" in logged_in.get(reverse("web:dashboard")).content

    def test_an_unrecognised_prefix_shows_as_rtx(self, logged_in, active_config, make_sample):
        """Modality is a stored column now, and an unknown batch prefix defaults to RTX,
        so no row on the dashboard is left without a workflow."""
        sample = make_sample("ODD-1", batch_name_from_vendor="ZZZ-1")

        assert sample.modality == "RTX"
        assert b"ODD-1" in logged_in.get(reverse("web:dashboard")).content

    def test_filter_options_are_not_repeated(self, logged_in, make_sample):
        """Meta.ordering leaking into DISTINCT repeats every option once per sample."""
        make_sample("A-1", batch_name_from_vendor="MTX-22068")
        make_sample("A-2", batch_name_from_vendor="MTX-22068")

        response = logged_in.get(reverse("web:dashboard"))

        assert response.context["organisms"] == ["mouse"]
        assert response.context["batches"] == ["MTX-22068"]

    def test_shows_the_default_columns(self, logged_in, make_sample):
        make_sample("READY-1")

        response = logged_in.get(reverse("web:dashboard"))

        # Asserted on the rendered column set rather than the page, because every label
        # also appears in the column-picker menu.
        keys = [column.key for column in response.context["columns"]]
        assert "library_prep_method_name" in keys
        assert "sequencing_vendor" not in keys

    def test_choosing_columns_changes_the_table(self, logged_in, make_sample, user):
        make_sample("READY-1")

        logged_in.post(reverse("web:set-columns"), {"columns": ["fastq_name", "sequencing_vendor"]})

        response = logged_in.get(reverse("web:dashboard"))
        user.refresh_from_db()
        assert user.visible_columns == ["fastq_name", "sequencing_vendor"]
        assert [column.key for column in response.context["columns"]] == [
            "fastq_name",
            "sequencing_vendor",
        ]

    def test_fastq_name_cannot_be_hidden(self, logged_in, make_sample, user):
        """Hiding the identifying column leaves a table nobody can read."""
        make_sample("READY-1")

        logged_in.post(reverse("web:set-columns"), {"columns": ["organism_common_name"]})

        user.refresh_from_db()
        assert user.visible_columns[0] == "fastq_name"

    def test_column_choices_survive_a_new_session(self, logged_in, make_sample, client, user):
        make_sample("READY-1")
        logged_in.post(reverse("web:set-columns"), {"columns": ["fastq_name", "sample_type"]})

        client.force_login(user)

        assert b"Sample Type" in client.get(reverse("web:dashboard")).content

    def test_the_column_menu_offers_every_column_exactly_once(self, logged_in, make_sample):
        """The chooser is built from sections now, and a column filed under no section , or
        under two , would silently vanish from it or appear twice."""
        make_sample("READY-1")

        response = logged_in.get(reverse("web:dashboard"))

        grouped = [column.key for group in response.context["column_groups"] for column in group.columns]
        assert sorted(grouped) == sorted(column.key for column in columns.COLUMNS)

    def test_the_column_menu_offers_a_way_back_to_the_defaults(self, logged_in, make_sample):
        make_sample("READY-1")

        response = logged_in.get(reverse("web:dashboard"))

        assert response.context["default_column_keys"] == columns.DEFAULT_COLUMNS

    def test_filters_by_organism(self, logged_in, make_sample):
        make_sample("MOUSE-1", organism_common_name="mouse")
        make_sample("HUMAN-1", organism_common_name="human")

        response = logged_in.get(reverse("web:dashboard"), {"organism_common_name": "human"})

        assert b"HUMAN-1" in response.content
        assert b"MOUSE-1" not in response.content

    def test_filters_by_stage_status(self, logged_in, make_sample):
        make_sample("DONE-1", align="COMPLETED")
        make_sample("TODO-1")

        response = logged_in.get(reverse("web:dashboard"), {"align_status": "COMPLETED"})

        assert b"DONE-1" in response.content
        assert b"TODO-1" not in response.content

    def test_filters_by_a_stage_that_never_ran(self, logged_in, make_sample):
        make_sample("DONE-1", align="COMPLETED")
        make_sample("TODO-1")

        response = logged_in.get(reverse("web:dashboard"), {"align_status": NOT_COMPLETED})

        assert b"TODO-1" in response.content
        assert b"DONE-1" not in response.content

    def test_filters_by_batch(self, logged_in, make_sample):
        make_sample("A-1", batch_name_from_vendor="MTX-22068")
        make_sample("B-1", batch_name_from_vendor="RTX-34056")

        response = logged_in.get(reverse("web:dashboard"), {"batch_name_from_vendor": "MTX-22068"})

        assert b"A-1" in response.content
        assert b"B-1" not in response.content

    def test_refresh_status_re_reads_the_posted_rows_from_ocs(self, logged_in, monkeypatch, make_sample):
        from apps.catalog.services import sync as sync_service

        make_sample("A-1")
        make_sample("B-1")
        refreshed = []
        monkeypatch.setattr(
            sync_service,
            "sync_stage_statuses",
            lambda samples: refreshed.extend(sample.fastq_name for sample in samples),
        )

        response = logged_in.post(reverse("web:refresh-status"), {"fastq_names": ["A-1"]}, follow=True)

        assert refreshed == ["A-1"]
        assert b"Refreshed status for 1 samples" in response.content

    def test_refresh_status_survives_ocs_being_unreachable(self, logged_in, monkeypatch, make_sample):
        """The mirror is still readable; only the live read failed, and the table stays up."""
        from botocore.exceptions import EndpointConnectionError

        from apps.catalog.services import sync as sync_service

        make_sample("A-1")

        def _boom(samples):
            raise EndpointConnectionError(endpoint_url="https://dynamodb.us-west-2.amazonaws.com")

        monkeypatch.setattr(sync_service, "sync_stage_statuses", _boom)

        response = logged_in.post(reverse("web:refresh-status"), {"fastq_names": ["A-1"]}, follow=True)

        assert response.status_code == 200
        assert b"Could not reach OCS" in response.content

    def test_sync_pulls_a_batch(self, logged_in, monkeypatch, make_sample):
        from apps.catalog.services import sync as sync_service

        monkeypatch.setattr(sync_service, "sync_batch", lambda batch_name_from_vendor: [make_sample("NEW-1")])

        response = logged_in.post(reverse("web:sync"), {"batch_name_from_vendor": "MTX-22068"}, follow=True)

        assert b"Synced 1 samples" in response.content


class TestSubmitReview:
    """Step 1 , the submit modal."""

    def test_groups_submissions_by_stage(self, logged_in, active_config, make_sample):
        make_sample("TO-ALIGN")
        make_sample("TO-QC", align="COMPLETED")

        response = logged_in.post(reverse("web:submit-review"), {"fastq_names": ["TO-ALIGN", "TO-QC"]})

        assert b"Alignment" in response.content
        # The modal names the stage the way the rest of the product does — Stage.POST_ALIGN's
        # label — rather than "Post-QC", which appeared nowhere else.
        assert b"Post-alignment" in response.content
        assert not QueueEntry.objects.exists()

    def test_lists_what_will_not_be_submitted(self, logged_in, active_config, make_sample):
        make_sample("WAITING-1", ingest=NOT_COMPLETED)

        response = logged_in.post(reverse("web:submit-review"), {"fastq_names": ["WAITING-1"]})

        assert b"ingest_incomplete" in response.content

    def test_asks_for_a_workflow_the_config_cannot_run(self, logged_in, active_config, make_sample):
        """RFX is resolved from the batch name; this config just has no RFX workflow."""
        make_sample("ODD-1", batch_name_from_vendor="RFX-1")

        response = logged_in.post(reverse("web:submit-review"), {"fastq_names": ["ODD-1"]})

        assert b"Unknown Workflow" in response.content
        assert b"Select a workflow" in response.content

    def test_an_unrecognised_prefix_no_longer_asks(self, logged_in, active_config, make_sample):
        """The regression this replaced: 98% of the mirror rendered as an unknown workflow."""
        make_sample("ODD-2", batch_name_from_vendor="10X120", library_prep_method_name="10xV4")

        response = logged_in.post(reverse("web:submit-review"), {"fastq_names": ["ODD-2"]})

        assert b"Unknown Workflow" not in response.content

    def test_asks_for_an_asset_when_the_library_prep_is_unlisted(self, logged_in, active_config, make_sample):
        make_sample("ODD-PREP", library_prep_method_name="10xNotConfigured")

        response = logged_in.post(reverse("web:submit-review"), {"fastq_names": ["ODD-PREP"]})

        assert b"Unknown Library Prep" in response.content
        assert b"Select an asset" in response.content
        # The options are the config's own entries, not free text, and each carries the
        # stage and prep it answers for.
        assert b"align::10xNotConfigured::default" in response.content

    def test_selecting_an_asset_produces_a_command(self, logged_in, active_config, make_sample):
        make_sample("ODD-PREP", library_prep_method_name="10xNotConfigured")

        response = logged_in.post(
            reverse("web:submit-commands"),
            {
                "fastq_names": ["ODD-PREP"],
                "command_config_choice": ["align::10xNotConfigured::default"],
            },
        )

        assert b"ocs fastqs align tenx-arc" in response.content
        assert not QueueEntry.objects.exists()

    def test_nothing_selected_is_refused(self, logged_in, active_config):
        response = logged_in.post(reverse("web:submit-review"), {"fastq_names": []}, follow=True)

        assert b"Select at least one sample" in response.content

    def test_without_an_active_config_it_says_so(self, logged_in, make_sample):
        make_sample("READY-1")

        response = logged_in.post(reverse("web:submit-review"), {"fastq_names": ["READY-1"]}, follow=True)

        assert b"No active workflow config" in response.content


class TestSubmitCommands:
    """Step 2 , the confirmation modal."""

    def test_shows_the_command_and_the_notification_email(self, logged_in, active_config, make_sample, user):
        make_sample("READY-1")

        response = logged_in.post(reverse("web:submit-commands"), {"fastq_names": ["READY-1"]})

        assert b"Confirm Submission" in response.content
        assert b"ocs fastqs align tenx-arc" in response.content
        assert user.email.encode() in response.content
        assert not QueueEntry.objects.exists()


class TestSubmitConfirm:
    """Step 3 , queueing."""

    def test_queues_the_job(self, logged_in, active_config, make_sample):
        make_sample("READY-1")

        response = logged_in.post(reverse("web:submit-confirm"), {"fastq_names": ["READY-1"]}, follow=True)

        assert b"Queued 1 jobs" in response.content
        assert QueueEntry.objects.get().sample.fastq_name == "READY-1"

    def test_uses_the_email_from_the_final_step(self, logged_in, active_config, make_sample):
        make_sample("READY-1")

        logged_in.post(
            reverse("web:submit-confirm"),
            {"fastq_names": ["READY-1"], "email": "someone.else@alleninstitute.org"},
        )

        entry = QueueEntry.objects.get()
        assert entry.notify_email == "someone.else@alleninstitute.org"
        assert "someone.else@alleninstitute.org" in entry.command

    def test_an_unresolved_workflow_blocks_it(self, logged_in, active_config, make_sample):
        make_sample("ODD-1", batch_name_from_vendor="ZZZ-1")

        logged_in.post(reverse("web:submit-confirm"), {"fastq_names": ["ODD-1"]}, follow=True)

        assert not QueueEntry.objects.exists()

    def test_a_chosen_workflow_lets_it_through(self, logged_in, active_config, make_sample):
        make_sample("ODD-1", batch_name_from_vendor="ZZZ-1")

        logged_in.post(reverse("web:submit-confirm"), {"fastq_names": ["ODD-1"], "modality": "MTX"})

        assert QueueEntry.objects.get().modality_source == "user_confirmed"

    def test_a_chosen_asset_lets_an_unlisted_prep_through(self, logged_in, active_config, make_sample):
        make_sample("ODD-PREP", library_prep_method_name="10xNotConfigured")

        logged_in.post(
            reverse("web:submit-confirm"),
            {
                "fastq_names": ["ODD-PREP"],
                "command_config_choice": ["align::10xNotConfigured::default"],
            },
        )

        assert QueueEntry.objects.get().stage == Stage.ALIGN


class TestQueue:
    def test_lists_pending_entries_and_the_next_one(self, logged_in, queued):
        queued("READY-1")

        response = logged_in.get(reverse("web:queue"))

        assert b"READY-1" in response.content
        assert b"Next in queue" in response.content

    def test_users_do_not_see_each_others_queues(self, logged_in, queued, client, django_user_model):
        queued("READY-1")
        other = django_user_model.objects.create_user(username="other", email="o@b.org")
        client.force_login(other)

        assert b"READY-1" not in client.get(reverse("web:queue")).content

    def test_process_asks_the_worker_to_run(self, logged_in, queued, monkeypatch):
        queued("READY-1")
        called = []
        monkeypatch.setattr("apps.web.views.process_next_queue_entry.delay", lambda: called.append(True))

        logged_in.post(reverse("web:process-now"), follow=True)

        assert called == [True]

    def test_cancelling_a_pending_entry(self, logged_in, queued):
        entry = queued("READY-1")

        logged_in.post(reverse("web:cancel", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert entry.status == QueueEntry.Status.CANCELLED


class TestJobMonitor:
    """The monitor reads the mirror, so it covers OCS work this app never submitted.

    Driving it from QueueEntry meant an operator watching a busy pipeline saw an empty
    page whenever the demands had been submitted by hand, and meant a job vanished from
    the page the moment somebody deleted its queue entry.
    """

    def test_a_running_stage_appears(self, logged_in, make_sample):
        sample = make_sample("RUNNING-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="demand-123")

        response = logged_in.get(reverse("web:job-monitor"))

        assert b"RUNNING-1" in response.content
        assert b"demand-123" in response.content
        assert response.context["counts"]["align"] == 1

    def test_a_demand_submitted_outside_omicshub_is_shown_and_labelled(self, logged_in, make_sample):
        """The whole point: no queue entry holds this demand id, and it still appears."""
        sample = make_sample("EXTERNAL-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="not-ours")

        response = logged_in.get(reverse("web:job-monitor"))

        assert b"EXTERNAL-1" in response.content
        assert not response.context["running"][0].queued_here
        assert b"External" in response.content

    def test_a_demand_this_app_queued_is_labelled_as_such(self, logged_in, queued):
        entry = queued("OURS-1")
        entry.status = QueueEntry.Status.SUBMITTED
        entry.demand_id = "demand-ours"
        entry.save()
        entry.sample.stage_statuses.create(
            stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="demand-ours"
        )

        response = logged_in.get(reverse("web:job-monitor"))

        assert response.context["running"][0].queued_here
        assert b"OmicsHub" in response.content

    def test_a_finished_stage_moves_to_the_finished_table(self, logged_in, make_sample):
        sample = make_sample("DONE-1")
        sample.stage_statuses.create(
            stage=Stage.ALIGN, status="COMPLETED", demand_id="demand-done", duration_seconds=10080
        )

        response = logged_in.get(reverse("web:job-monitor"))

        assert not response.context["running"]
        assert [row.sample.fastq_name for row in response.context["finished"]] == ["DONE-1"]
        assert b"2h 48m" in response.content

    def test_a_failed_stage_is_finished_rather_than_running(self, logged_in, make_sample):
        """FAILED and ABORTED are outcomes. Left out of both tables they vanish entirely."""
        sample = make_sample("FAILED-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="FAILED", demand_id="demand-bad")

        response = logged_in.get(reverse("web:job-monitor"))

        assert [row.status for row in response.context["finished"]] == ["FAILED"]

    def test_a_stage_ocs_has_never_run_is_not_a_job(self, logged_in, make_sample):
        """`make_sample` writes an ingest row with a demand id and nothing else; a stage
        with no demand is a row the sweep created, not work anyone submitted."""
        sample = make_sample("IDLE-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="NOT COMPLETED", demand_id="")

        response = logged_in.get(reverse("web:job-monitor"))

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

        response = logged_in.get(reverse("web:job-monitor"))

        assert b"THEIRS-1" in response.content

    def test_the_row_count_does_not_grow_with_the_number_of_jobs(
        self, logged_in, make_sample, django_assert_num_queries
    ):
        """One query for running, one for finished — not one per sample for the name."""
        for index in range(6):
            sample = make_sample(f"MANY-{index}")
            sample.stage_statuses.create(
                stage=Stage.ALIGN, status="IN_PROGRESS", demand_id=f"demand-{index}"
            )
        logged_in.get(reverse("web:job-monitor"))

        with django_assert_num_queries(6):
            logged_in.get(reverse("web:job-monitor"))


class TestFailedJobs:
    def test_lists_failures_with_the_error(self, logged_in, queued):
        entry = queued("BAD-1")
        entry.status = QueueEntry.Status.FAILED
        entry.error_message = "OCS rejected the demand"
        entry.save()

        response = logged_in.get(reverse("web:failed"))

        assert b"OCS rejected the demand" in response.content

    def test_retry_puts_it_back_on_the_queue(self, logged_in, queued):
        entry = queued("BAD-1")
        entry.status = QueueEntry.Status.FAILED
        entry.error_message = "boom"
        entry.save()

        logged_in.post(reverse("web:retry", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert entry.status == QueueEntry.Status.PENDING
        assert entry.error_message == ""

    def test_a_stranded_entry_is_not_retryable(self, logged_in, queued):
        """It may already be running at OCS."""
        entry = queued("STRANDED-1")
        entry.status = QueueEntry.Status.STRANDED
        entry.save()

        response = logged_in.post(reverse("web:retry", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert entry.status == QueueEntry.Status.STRANDED
        assert b"Check OCS" in response.content

    def test_delete_removes_the_entry(self, logged_in, queued):
        entry = queued("BAD-1")
        entry.status = QueueEntry.Status.FAILED
        entry.save()

        logged_in.post(reverse("web:delete-job", args=[entry.pk]), follow=True)

        assert not QueueEntry.objects.filter(pk=entry.pk).exists()

    def test_a_submitted_entry_cannot_be_deleted(self, logged_in, queued):
        entry = queued("RUNNING-1")
        entry.status = QueueEntry.Status.SUBMITTED
        entry.save()

        logged_in.post(reverse("web:delete-job", args=[entry.pk]), follow=True)

        assert QueueEntry.objects.filter(pk=entry.pk).exists()
