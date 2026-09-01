"""The review -> commands -> confirm submission entry wizard."""

from __future__ import annotations

import json

import pytest
from django.urls import reverse

from apps.sample_catalog.models import NOT_COMPLETED, Stage
from apps.submission_queue.models import CartItem, QueueEntry
from apps.workflow_engine.models import WorkflowConfig

from .conftest import messages_in

pytestmark = pytest.mark.django_db


class TestSubmitReview:
    """Step 1 , the submit modal."""

    def test_ajax_review_returns_only_the_modal(self, logged_in, active_config, make_sample):
        make_sample("READY-1")

        response = logged_in.post(
            reverse("web_ui:submit-review"),
            {"fastq_names": ["READY-1"]},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert response.status_code == 200
        assert response.templates[0].name == "partials/submission_review_modal.html"
        assert b'id="submit-modal"' in response.content
        assert b'id="checkout-form"' not in response.content

    def test_shows_the_notification_email_editor(self, logged_in, active_config, make_sample, user):
        make_sample("READY-1")

        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["READY-1"]})

        assert b"Notification Email" in response.content
        assert b'id="submit-notification-email"' in response.content
        assert user.email.encode() in response.content

    def test_groups_submissions_by_stage(self, logged_in, active_config, make_sample):
        make_sample("TO-ALIGN")
        make_sample("TO-QC", align="COMPLETED")

        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["TO-ALIGN", "TO-QC"]})

        assert b"Alignment" in response.content
        # The modal uses Stage.POST_ALIGN's label rather than "Post-QC", which appeared
        # nowhere else.
        assert b"Post-alignment" in response.content
        assert not QueueEntry.objects.exists()

    def test_lists_what_will_not_be_submitted(self, logged_in, active_config, make_sample):
        make_sample("WAITING-1", ingest=NOT_COMPLETED)

        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["WAITING-1"]})

        assert b"ingest_incomplete" in response.content

    def test_asks_for_a_workflow_the_config_cannot_run(self, logged_in, active_config, make_sample):
        """RFX is resolved from the batch name; this config just has no RFX workflow."""
        make_sample("ODD-1", batch_name_from_vendor="RFX-1")

        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["ODD-1"]})

        assert b"Unknown Workflow" in response.content
        assert b"Select a workflow" in response.content

    def test_an_unrecognised_prefix_no_longer_asks(self, logged_in, active_config, make_sample):
        """The regression this replaced: 98% of the local database rendered as an unknown workflow."""
        make_sample("ODD-2", batch_name_from_vendor="10X120", library_prep_method_name="10xV4")

        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["ODD-2"]})

        assert b"Unknown Workflow" not in response.content

    def test_asks_for_an_asset_when_the_library_prep_is_unlisted(self, logged_in, active_config, make_sample):
        make_sample("ODD-PREP", library_prep_method_name="10xNotConfigured")

        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["ODD-PREP"]})

        assert b"Unknown Library Prep" in response.content
        assert b"Select an asset" in response.content
        # The options are the config's own entries, not free text, and each carries the
        # stage and prep it answers for.
        assert b"align::10xNotConfigured::default" in response.content

    def test_selecting_an_asset_produces_a_command(self, logged_in, active_config, make_sample):
        make_sample("ODD-PREP", library_prep_method_name="10xNotConfigured")

        response = logged_in.post(
            reverse("web_ui:submit-commands"),
            {
                "fastq_names": ["ODD-PREP"],
                "command_config_choice": ["align::10xNotConfigured::default"],
            },
        )

        assert b"ocs fastqs align tenx-arc" in response.content
        assert not QueueEntry.objects.exists()

    def test_nothing_selected_is_refused(self, logged_in, active_config):
        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": []}, follow=True)

        assert b"Select at least one sample" in response.content

    def test_without_an_active_config_it_says_so(self, logged_in, make_sample):
        make_sample("READY-1")

        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["READY-1"]}, follow=True)

        assert b"No active workflow config" in response.content


class TestSubmitCommands:
    """Step 2 , the confirmation modal."""

    def test_ajax_confirm_returns_only_the_modal(self, logged_in, active_config, make_sample):
        make_sample("READY-1")

        response = logged_in.post(
            reverse("web_ui:submit-commands"),
            {"fastq_names": ["READY-1"]},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert response.status_code == 200
        assert response.templates[0].name == "partials/submission_confirmation_modal.html"
        assert b'id="final-modal"' in response.content
        assert b'id="checkout-form"' not in response.content

    def test_shows_the_command_without_a_notification_email_editor(
        self, logged_in, active_config, make_sample, user
    ):
        make_sample("READY-1")

        response = logged_in.post(reverse("web_ui:submit-commands"), {"fastq_names": ["READY-1"]})

        assert b"Confirm Submission" in response.content
        assert b"ocs fastqs align tenx-arc" in response.content
        assert user.email.encode() in response.content
        assert b'id="global-notification-email"' not in response.content
        # The response contains the hidden review modal as well as the open confirmation
        # modal. The editor must appear before, not inside, the confirmation modal.
        assert response.content.index(b"Notification Email") < response.content.index(b'id="final-modal"')
        assert b'type="hidden" name="email"' in response.content
        assert not QueueEntry.objects.exists()


class TestSubmitConfirm:
    """Step 3 , queueing."""

    def test_queues_the_job(self, logged_in, active_config, make_sample):
        make_sample("READY-1")

        response = logged_in.post(reverse("web_ui:submit-confirm"), {"fastq_names": ["READY-1"]}, follow=True)

        assert b"Queued 1 jobs" in response.content
        assert QueueEntry.objects.get().sample.fastq_name == "READY-1"

    def test_uses_the_email_from_the_final_step(self, logged_in, active_config, make_sample):
        make_sample("READY-1")

        logged_in.post(
            reverse("web_ui:submit-confirm"),
            {"fastq_names": ["READY-1"], "email": "someone.else@alleninstitute.org"},
        )

        entry = QueueEntry.objects.get()
        assert entry.notify_email == "someone.else@alleninstitute.org"
        assert "someone.else@alleninstitute.org" in entry.command

    def test_an_unresolved_workflow_blocks_it(self, logged_in, active_config, make_sample):
        make_sample("ODD-1", batch_name_from_vendor="ZZZ-1")

        logged_in.post(reverse("web_ui:submit-confirm"), {"fastq_names": ["ODD-1"]}, follow=True)

        assert not QueueEntry.objects.exists()

    def test_a_chosen_workflow_lets_it_through(self, logged_in, active_config, make_sample):
        make_sample("ODD-1", batch_name_from_vendor="ZZZ-1")

        logged_in.post(reverse("web_ui:submit-confirm"), {"fastq_names": ["ODD-1"], "modality": "MTX"})

        assert QueueEntry.objects.get().modality_source == "user_confirmed"

    def test_a_chosen_asset_lets_an_unlisted_prep_through(self, logged_in, active_config, make_sample):
        make_sample("ODD-PREP", library_prep_method_name="10xNotConfigured")

        logged_in.post(
            reverse("web_ui:submit-confirm"),
            {
                "fastq_names": ["ODD-PREP"],
                "command_config_choice": ["align::10xNotConfigured::default"],
            },
        )

        assert QueueEntry.objects.get().stage == Stage.ALIGN


class TestSubmissionJourney:
    def test_the_three_steps_lead_to_a_queued_job(self, logged_in, active_config, make_sample, user):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        checkout = logged_in.get(reverse("web_ui:checkout"))
        assert [item.sample.fastq_name for item in checkout.context["cart_items"]] == ["READY-1"]

        step_one = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["READY-1"]})
        assert step_one.context["open_modal"] == "submit"
        assert step_one.context["plan"].entries[0].command.startswith("ocs fastqs align tenx-arc")

        step_two = logged_in.post(reverse("web_ui:submit-commands"), {"fastq_names": ["READY-1"]})
        assert step_two.context["open_modal"] == "final"
        assert user.email.encode() in step_two.content

        step_three = logged_in.post(
            reverse("web_ui:submit-confirm"), {"fastq_names": ["READY-1"]}, follow=True
        )
        assert b"Queued 1 jobs" in step_three.content
        assert QueueEntry.objects.get().sample.fastq_name == "READY-1"
        # Only what reached the queue leaves the cart.
        assert not CartItem.objects.filter(user=user).exists()

    def test_an_explicitly_picked_config_beats_the_active_one(
        self, logged_in, active_config, config, make_sample, user, review
    ):
        make_sample("READY-1")
        variant = json.loads(json.dumps(config))
        variant["workflows"]["MTX"]["alignment_command_configs"][0]["command"] = [
            "ocs",
            "fastqs",
            "align",
            "tenx-arc-preview",
        ]
        other = WorkflowConfig.objects.create(
            name="preview.jsonc", raw="{}", data=variant, uploaded_by=user, is_active=False
        )

        response = review(["READY-1"], config_id=other.pk)

        assert response.context["config"].pk == other.pk
        assert response.context["plan"].entries[0].command.startswith("ocs fastqs align tenx-arc-preview")
        # And the active one is still what an unqualified submission uses.
        assert review(["READY-1"]).context["config"].pk == active_config.pk

    def test_forcing_alignment_reruns_a_stage_that_is_already_complete(
        self, logged_in, active_config, make_sample, review, submit
    ):
        make_sample("DONE-1", align="COMPLETED", postalign="COMPLETED")

        without_force = review(["DONE-1"])
        assert without_force.context["plan"].entries == []

        with_force = review(["DONE-1"], force=Stage.ALIGN.value)
        assert [entry.stage for entry in with_force.context["plan"].entries] == [Stage.ALIGN]

        submit(["DONE-1"], force=Stage.ALIGN.value)
        assert QueueEntry.objects.get().forced is True

    def test_forcing_post_alignment_without_an_alignment_explains_itself(
        self, logged_in, active_config, make_sample, review
    ):
        make_sample("UNALIGNED-1")

        response = review(["UNALIGNED-1"], force=Stage.POST_ALIGN.value)

        skip = response.context["plan"].skipped[0]
        assert skip.reason == "alignment_incomplete"
        assert "no output to run QC over" in skip.detail
        assert b"no output to run QC over" in response.content

    def test_batch_processing_switches_the_command_to_fastq_names(
        self, logged_in, active_config, make_sample, review
    ):
        make_sample(
            "RTX-1",
            batch_name_from_vendor="RTX-900",
            organism_common_name="human",
            library_prep_method_name="10xV4",
            load_name="LOAD_RTX",
        )

        plain = review(["RTX-1"]).context["plan"].entries[0].command
        batched = review(["RTX-1"], batch_processing="on").context["plan"].entries[0].command

        assert "--load-names LOAD_RTX" in plain
        assert "--fastq-names RTX-1" in batched

    def test_a_per_sample_reference_override_changes_only_that_command(
        self, logged_in, active_config, make_sample, review
    ):
        make_sample("READY-1")
        make_sample("READY-2")

        response = review(["READY-1", "READY-2"], **{"override__READY-1__reference_name": "mouse_rtx_ref"})

        commands = {e.sample.fastq_name: e.command for e in response.context["plan"].entries}
        assert "--reference-names mouse_rtx_ref" in commands["READY-1"]
        assert "--reference-names mouse_mtx_ref" in commands["READY-2"]

    def test_a_hand_edited_command_is_what_gets_queued(self, logged_in, active_config, make_sample, submit):
        make_sample("READY-1")

        submit(
            ["READY-1"],
            **{
                "override__READY-1__command": 'ocs fastqs align tenx-arc --reference-names "my ref"',
                "override__READY-1__command_original": "ocs fastqs align tenx-arc",
            },
        )

        entry = QueueEntry.objects.get()
        # shlex, not a whitespace split: the quoted reference stays one argv element.
        assert entry.command_args == ["ocs", "fastqs", "align", "tenx-arc", "--reference-names", "my ref"]

    def test_an_unbalanced_quote_holds_back_one_sample_not_the_whole_plan(
        self, logged_in, active_config, make_sample, review
    ):
        make_sample("READY-1")
        make_sample("READY-2")

        response = review(
            ["READY-1", "READY-2"],
            **{
                "override__READY-1__command": 'ocs fastqs align tenx-arc --reference-names "unclosed',
                "override__READY-1__command_original": "ocs fastqs align tenx-arc",
            },
        )

        plan = response.context["plan"]
        assert [entry.sample.fastq_name for entry in plan.entries] == ["READY-2"]
        assert "could not be read" in plan.skipped[0].detail
        assert b"could not be read" in response.content

    def test_choosing_a_workflow_for_an_unlisted_library_prep(
        self, logged_in, active_config, make_sample, review, submit
    ):
        make_sample("ODD-PREP", library_prep_method_name="10xSomethingNew")

        asked = review(["ODD-PREP"])
        group = asked.context["unconfigured_groups"][0]
        assert group["library_prep_method_name"] == "10xSomethingNew"
        assert [option["name"] for option in group["options"]] == ["default"]

        chosen = review(["ODD-PREP"], command_config_choice=f"{Stage.ALIGN.value}::10xSomethingNew::default")
        assert len(chosen.context["plan"].entries) == 1

        submit(["ODD-PREP"], command_config_choice=f"{Stage.ALIGN.value}::10xSomethingNew::default")
        assert QueueEntry.objects.count() == 1

    def test_a_malformed_workflow_choice_is_ignored_rather_than_crashing(
        self, logged_in, active_config, make_sample, review
    ):
        make_sample("ODD-PREP", library_prep_method_name="10xSomethingNew")

        response = review(["ODD-PREP"], command_config_choice="nonsense-with-no-separators")

        assert response.status_code == 200
        assert response.context["unconfigured_groups"]

    def test_submitting_nothing_is_refused(self, logged_in, active_config):
        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": []}, follow=True)

        assert b"Select at least one sample to submit" in response.content
        assert not QueueEntry.objects.exists()

    def test_a_selection_where_every_sample_is_skipped_queues_nothing_and_says_so(
        self, logged_in, active_config, make_sample, submit
    ):
        make_sample("WAITING-1", ingest=NOT_COMPLETED)
        make_sample("DONE-1", align="COMPLETED", postalign="COMPLETED")

        response = submit(["WAITING-1", "DONE-1"])

        assert b"Nothing was queued" in response.content
        assert not QueueEntry.objects.exists()

    def test_every_skipped_sample_gets_a_reason_on_screen(
        self, logged_in, active_config, make_sample, review
    ):
        make_sample("WAITING-1", ingest=NOT_COMPLETED)
        make_sample("DONE-1", align="COMPLETED", postalign="COMPLETED")
        make_sample("RUNNING-1", align="IN_PROGRESS")

        response = review(["WAITING-1", "DONE-1", "RUNNING-1"])

        plan = response.context["plan"]
        html = messages_in(response)
        assert len(plan.skipped) == 3
        for skip in plan.skipped:
            assert skip.detail, f"{skip.sample.fastq_name} was skipped with no explanation"
            assert skip.sample.fastq_name in html
            assert skip.detail.split(":")[0][:40] in html

    def test_a_skipped_sample_stays_in_the_cart_for_next_time(
        self, logged_in, active_config, make_sample, user
    ):
        make_sample("READY-1")
        make_sample("WAITING-1", ingest=NOT_COMPLETED)
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1", "WAITING-1"]})

        logged_in.post(reverse("web_ui:submit-confirm"), {"fastq_names": ["READY-1", "WAITING-1"]})

        staged = set(CartItem.objects.filter(user=user).values_list("sample__fastq_name", flat=True))
        assert staged == {"WAITING-1"}

    def test_confirming_the_same_plan_twice_queues_one_job(
        self, logged_in, active_config, make_sample, submit
    ):
        make_sample("READY-1")

        submit(["READY-1"])
        second = submit(["READY-1"])

        assert b"1 already queued; left alone" in second.content
        assert QueueEntry.objects.count() == 1

    def test_a_bad_notification_address_is_refused_before_anything_is_queued(
        self, logged_in, active_config, make_sample
    ):
        make_sample("READY-1")

        response = logged_in.post(
            reverse("web_ui:submit-confirm"),
            {"fastq_names": ["READY-1"], "email": "not-an-address"},
            follow=True,
        )

        assert b"Enter a valid email address" in response.content
        assert not QueueEntry.objects.exists()

    def test_without_an_active_config_the_flow_says_what_is_missing(self, logged_in, make_sample):
        make_sample("READY-1")

        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["READY-1"]}, follow=True)

        assert b"No active workflow config" in response.content

    def test_the_command_preview_answers_for_one_sample_at_a_time(
        self, logged_in, active_config, make_sample
    ):
        make_sample("READY-1")

        response = logged_in.post(
            reverse("web_ui:command-preview"),
            {
                "fastq_names": ["READY-1"],
                "fastq_name": "READY-1",
                "override__READY-1__reference_name": "mouse_rtx_ref",
            },
        )

        assert response.status_code == 200
        assert "--reference-names mouse_rtx_ref" in response.json()["command"]

    def test_previewing_a_sample_that_cannot_run_returns_the_reason(
        self, logged_in, active_config, make_sample
    ):
        make_sample("WAITING-1", ingest=NOT_COMPLETED)

        response = logged_in.post(reverse("web_ui:command-preview"), {"fastq_name": "WAITING-1"})

        assert response.status_code == 409
        assert response.json()["reason"] == "ingest_incomplete"

    def test_previewing_an_unknown_sample_is_a_404_not_a_500(self, logged_in, active_config):
        response = logged_in.post(reverse("web_ui:command-preview"), {"fastq_name": "GHOST-1"})

        assert response.status_code == 404
        assert "GHOST-1" in response.json()["error"]
