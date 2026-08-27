"""Submission, checkout, and workflow configuration tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.sample_catalog.models import NOT_COMPLETED, Stage
from apps.submission_queue.models import CartItem, QueueEntry
from apps.workflow_engine.models import WorkflowConfig

pytestmark = pytest.mark.django_db


TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def messages_in(response) -> str:
    return response.content.decode()


def config_upload(data: dict, name: str = "config.jsonc") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, json.dumps(data).encode(), content_type="application/json")


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
        """The regression this replaced: 98% of the mirror rendered as an unknown workflow."""
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


class TestCartJourney:
    def test_the_badge_counts_what_is_staged(self, logged_in, make_sample):
        make_sample("READY-1")
        make_sample("READY-2")

        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1", "READY-2"]})

        assert logged_in.get(reverse("web_ui:dashboard")).context["cart_count"] == 2

    def test_add_the_same_sample_twice_then_remove_then_clear(self, logged_in, make_sample, user):
        make_sample("READY-1")
        make_sample("READY-2")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1", "READY-2"]})

        again = logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]}, follow=True)
        assert b"1 already in the cart" in again.content
        assert CartItem.objects.filter(user=user).count() == 2

        removed = logged_in.post(reverse("web_ui:cart-remove"), {"fastq_names": ["READY-1"]}, follow=True)
        assert b"Removed 1 sample from the cart" in removed.content
        assert logged_in.get(reverse("web_ui:dashboard")).context["cart_count"] == 1

        cleared = logged_in.post(reverse("web_ui:cart-clear"), follow=True)
        assert b"Cart emptied" in cleared.content
        assert not CartItem.objects.filter(user=user).exists()

    def test_a_fastq_name_the_mirror_no_longer_holds_is_reported(self, logged_in, make_sample, user):
        make_sample("READY-1")

        response = logged_in.post(
            reverse("web_ui:cart-add"), {"fastq_names": ["READY-1", "GHOST-1"]}, follow=True
        )

        assert b"Added 1 sample to the cart" in response.content
        assert b"1 no longer in the mirror" in response.content
        assert CartItem.objects.filter(user=user).count() == 1

    def test_a_cart_of_only_ghosts_says_so_rather_than_reporting_success(self, logged_in, user):
        response = logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["GHOST-1"]}, follow=True)

        assert b"1 no longer in the mirror" in response.content
        assert not CartItem.objects.filter(user=user).exists()

    def test_the_dashboards_add_button_answers_without_leaving_the_page(self, logged_in, make_sample):
        make_sample("READY-1")

        response = logged_in.post(
            reverse("web_ui:cart-add"),
            {"fastq_names": ["READY-1"]},
            headers={"x-requested-with": "XMLHttpRequest"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "error": "",
            "message": "Added 1 sample to the cart.",
            "added": 1,
            "already": 0,
            "missing": 0,
            "cart_count": 1,
        }

    def test_one_users_cart_is_their_own(self, logged_in, other_client, make_sample, other_user):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        assert other_client.get(reverse("web_ui:checkout")).context["cart_items"] == []
        assert not CartItem.objects.filter(user=other_user).exists()

    def test_the_partner_of_a_multiome_half_is_added_and_the_user_is_told(
        self, logged_in, active_config, make_sample, review
    ):
        make_sample(
            "GEX-1",
            batch_name_from_vendor="MTX-500",
            load_name="LOAD_PAIR",
            library_prep_method_name="10xMultX_GEX",
        )
        make_sample(
            "ATAC-1",
            batch_name_from_vendor="ATX-500",
            load_name="LOAD_PAIR",
            library_prep_method_name="10xMultX_ATAC",
        )

        response = review(["GEX-1"])

        # Report the partner added to the selected sample.
        assert b"Added 1 multiome partner(s) to the selection: ATAC-1." in response.content
        assert response.context["submission"]["fastq_names"] == ["GEX-1", "ATAC-1"]

    def test_the_review_modal_itself_accounts_for_the_partner_it_pulled_in(
        self, logged_in, active_config, make_sample, review
    ):
        """The banner announcing the partner sits behind the open modal, so the modal says it too."""
        make_sample(
            "GEX-1",
            batch_name_from_vendor="MTX-500",
            load_name="LOAD_PAIR",
            library_prep_method_name="10xMultX_GEX",
        )
        make_sample(
            "ATAC-1",
            batch_name_from_vendor="ATX-500",
            load_name="LOAD_PAIR",
            library_prep_method_name="10xMultX_ATAC",
        )

        response = review(["GEX-1"])

        assert response.context["plan"].covered_by_pair[0].fastq_name == "ATAC-1"
        html = messages_in(response)
        # Everything the reader can actually see inside the review modal. Hidden inputs are
        # stripped: the partner is carried forward in one, and a hidden field is not how
        # anyone learns that their selection grew.
        modal = re.sub(r'<input type="hidden"[^>]*>', "", html[html.index('id="submit-modal"') :])
        assert "covered-by-pair-note" in modal
        assert "ATAC-1" in modal

    def test_a_multiome_half_with_no_partner_plans_as_an_ordinary_sample(
        self, logged_in, active_config, make_sample, review
    ):
        """No load_name partner means no pair was intended; this sample plans exactly
        like any other , including a plain "library prep unconfigured" skip if its own
        prep is not one the active config's MTX workflow lists, with no multiome-specific
        message layered on top."""
        make_sample(
            "LONELY-ATAC",
            batch_name_from_vendor="ATX-501",
            load_name="LOAD_ALONE",
            library_prep_method_name="10xATAC_Mult",
        )

        response = review(["LONELY-ATAC"])

        plan = response.context["plan"]
        assert [skip.sample.fastq_name for skip in plan.skipped] == ["LONELY-ATAC"]
        assert plan.skipped[0].reason == "library_prep_unconfigured"
        assert b"No MTX pair found for" not in response.content


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


class TestSettingsPage:
    def test_an_ordinary_user_is_told_no_rather_than_bounced_to_sign_in(self, logged_in):
        response = logged_in.get(reverse("web_ui:configs"))

        assert response.status_code == 403

    def test_an_ordinary_user_cannot_activate_a_config_either(self, logged_in, active_config, config, user):
        spare = WorkflowConfig.objects.create(
            name="spare.jsonc", raw="{}", data=config, uploaded_by=user, is_active=False
        )

        response = logged_in.post(reverse("web_ui:activate-config", args=[spare.pk]))

        spare.refresh_from_db()
        assert response.status_code == 403
        assert spare.is_active is False

    def test_the_old_settings_path_still_lands_on_configs(self, staff_client):
        response = staff_client.get("/settings/")

        assert response.status_code == 302
        assert response["Location"] == reverse("web_ui:configs")

    def test_staff_can_upload_a_config_and_it_arrives_inactive(self, staff_client, config):
        response = staff_client.post(
            reverse("web_ui:configs"), {"file": config_upload(config, "good.jsonc")}, follow=True
        )

        uploaded = WorkflowConfig.objects.get(name="good.jsonc")
        assert b"Uploaded good.jsonc. Activate it to start using it." in response.content
        assert uploaded.is_active is False

    def test_a_config_that_is_not_json_is_rejected_and_named(self, staff_client):
        broken = SimpleUploadedFile("broken.jsonc", b"{ this is not json", content_type="application/json")

        response = staff_client.post(reverse("web_ui:configs"), {"file": broken}, follow=True)

        assert b"broken.jsonc was rejected" in response.content
        assert b"not valid JSON" in response.content
        assert not WorkflowConfig.objects.filter(name="broken.jsonc").exists()

    def test_a_config_missing_sections_names_the_sections(self, staff_client):
        thin = SimpleUploadedFile("thin.jsonc", b'{"references": {}}', content_type="application/json")

        response = staff_client.post(reverse("web_ui:configs"), {"file": thin}, follow=True)

        body = messages_in(response)
        assert "missing required keys" in body
        assert "workflows" in body and "status_mappings" in body
        assert not WorkflowConfig.objects.exists()

    def test_a_command_written_as_a_string_is_rejected_with_the_fix(self, staff_client, config):
        config["workflows"]["MTX"]["alignment_command_configs"][0]["command"] = "ocs fastqs align"

        response = staff_client.post(
            reverse("web_ui:configs"), {"file": config_upload(config, "stringly.jsonc")}, follow=True
        )

        assert b"must be a list of words" in response.content
        assert not WorkflowConfig.objects.exists()

    def test_a_file_that_is_not_utf8_text_is_rejected(self, staff_client):
        binary = SimpleUploadedFile("binary.jsonc", b"\xff\xfe\x00{\x00}", content_type="application/json")

        response = staff_client.post(reverse("web_ui:configs"), {"file": binary}, follow=True)

        assert b"not UTF-8 text" in response.content
        assert not WorkflowConfig.objects.exists()

    def test_an_oversized_file_is_refused_before_it_is_parsed(self, staff_client):
        huge = SimpleUploadedFile(
            "huge.jsonc", b"{" + b" " * (2 * 1024 * 1024) + b"}", content_type="application/json"
        )

        response = staff_client.post(reverse("web_ui:configs"), {"file": huge}, follow=True)

        assert b"Config files are under 2 MB" in response.content
        assert not WorkflowConfig.objects.exists()

    def test_uploading_nothing_is_refused(self, staff_client):
        response = staff_client.post(reverse("web_ui:configs"), {}, follow=True)

        assert response.status_code == 200
        assert b"This field is required" in response.content

    def test_activate_is_a_primary_button_that_confirms_the_global_effect(
        self, staff_client, config, staff_user
    ):
        """Activating changes every user's default, so it should not look or act like
        a routine secondary action."""
        WorkflowConfig.objects.create(
            name="spare.jsonc", raw="{}", data=config, uploaded_by=staff_user, is_active=False
        )

        response = staff_client.get(reverse("web_ui:configs"))
        text = response.content.decode()
        label_index = text.index('aria-label="Activate spare.jsonc')
        activate_button = text[text.rindex("<button", 0, label_index) : text.index("</button>", label_index)]

        assert "btn-primary" in activate_button
        assert "return confirm(" in activate_button
        assert "Every submission" in activate_button

    def test_activating_a_config_stands_the_previous_one_down(
        self, staff_client, active_config, config, staff_user
    ):
        replacement = WorkflowConfig.objects.create(
            name="replacement.jsonc", raw="{}", data=config, uploaded_by=staff_user, is_active=False
        )

        response = staff_client.post(reverse("web_ui:activate-config", args=[replacement.pk]), follow=True)

        active_config.refresh_from_db()
        replacement.refresh_from_db()
        assert b"replacement.jsonc is now active" in response.content
        assert replacement.is_active is True
        assert active_config.is_active is False
        assert WorkflowConfig.objects.filter(is_active=True).count() == 1

    def test_a_newly_activated_config_is_what_the_next_submission_uses(
        self, staff_client, logged_in, active_config, config, make_sample, staff_user, review
    ):
        make_sample("READY-1")
        variant = json.loads(json.dumps(config))
        variant["workflows"]["MTX"]["alignment_command_configs"][0]["command"] = [
            "ocs",
            "fastqs",
            "align",
            "tenx-arc-next",
        ]
        replacement = WorkflowConfig.objects.create(
            name="next.jsonc", raw="{}", data=variant, uploaded_by=staff_user, is_active=False
        )

        staff_client.post(reverse("web_ui:activate-config", args=[replacement.pk]))

        assert (
            review(["READY-1"])
            .context["plan"]
            .entries[0]
            .command.startswith("ocs fastqs align tenx-arc-next")
        )


class TestConfigDetail:
    def test_an_ordinary_user_can_view_it(self, logged_in, active_config):
        """Choosing which config drives your own submission is already staff-free
        (the checkout picker); reading one before you choose it is the same access."""
        response = logged_in.get(reverse("web_ui:config-detail", args=[active_config.pk]))

        assert response.status_code == 200

    def test_an_ordinary_user_is_sent_back_to_checkout_not_the_staff_only_list(
        self, logged_in, active_config
    ):
        response = logged_in.get(reverse("web_ui:config-detail", args=[active_config.pk]))

        assert b"Back to Checkout" in response.content
        assert b"Back to Configs" not in response.content
        assert reverse("web_ui:configs") not in response.content.decode()

    def test_staff_are_sent_back_to_the_configs_list(self, staff_client, active_config):
        response = staff_client.get(reverse("web_ui:config-detail", args=[active_config.pk]))

        assert b"Back to Configs" in response.content

    def test_checkout_links_any_user_to_the_config_they_are_using(self, logged_in, active_config):
        response = logged_in.get(reverse("web_ui:checkout"))

        assert reverse("web_ui:config-detail", args=[active_config.pk]) in response.content.decode()
        assert b"Upload a new config" not in response.content

    def test_checkout_only_shows_upload_to_staff(self, staff_client, active_config):
        response = staff_client.get(reverse("web_ui:checkout"))

        assert b"Upload a new config" in response.content

    def test_signed_out_is_sent_to_sign_in(self, client, active_config):
        target = reverse("web_ui:config-detail", args=[active_config.pk])

        response = client.get(target)

        assert response.status_code == 302
        assert response["Location"] == f"{reverse('login')}?next={target}"

    def test_the_configs_list_links_to_the_detail_page(self, staff_client, active_config):
        response = staff_client.get(reverse("web_ui:configs"))

        assert reverse("web_ui:config-detail", args=[active_config.pk]) in response.content.decode()

    def test_the_pretty_view_is_the_default_and_flattens_references(self, staff_client, active_config):
        """The fixture config covers all three reference shapes: a bare "all" modality, a
        direct modality string, and a modality nested by library prep."""
        response = staff_client.get(reverse("web_ui:config-detail", args=[active_config.pk]))

        assert response.status_code == 200
        assert response.context["view"] == "pretty"
        rows = {
            (row["organism"], row["modality"], row["library_prep"]): row["reference"]
            for row in response.context["reference_rows"]
        }
        assert rows[("human", "All", "All")] == "human_all_ref"
        assert rows[("mouse", "MTX", "All")] == "mouse_mtx_ref"
        assert rows[("mouse", "RTX", "All")] == "mouse_rtx_ref"
        assert rows[("rat", "RFX", "10xFXv2")] == "rat_fxv2_ref"
        assert b"human_all_ref" in response.content
        assert b"rat_fxv2_ref" in response.content

    def test_the_pretty_view_shows_job_settings_and_status_mappings(self, staff_client, active_config):
        response = staff_client.get(reverse("web_ui:config-detail", args=[active_config.pk]))

        assert b"Job Settings" in response.content
        assert response.context["job_settings"]["limit"] == 100
        assert {row["label"] for row in response.context["status_mapping_rows"]} == {
            "Ingest complete",
            "Alignment complete",
            "Post-alignment complete",
        }

    def test_the_raw_view_shows_the_uploaded_text_and_nothing_else(self, staff_client, config, staff_user):
        raw_config = WorkflowConfig.objects.create(
            name="raw-check.jsonc",
            raw="// a distinctive comment only the raw file has\n" + json.dumps(config),
            data=config,
            uploaded_by=staff_user,
        )

        response = staff_client.get(reverse("web_ui:config-detail", args=[raw_config.pk]), {"view": "raw"})

        assert response.context["view"] == "raw"
        assert b"a distinctive comment only the raw file has" in response.content
        assert b"Job Settings" not in response.content

    def test_an_invalid_view_falls_back_to_pretty(self, staff_client, active_config):
        response = staff_client.get(
            reverse("web_ui:config-detail", args=[active_config.pk]), {"view": "something-else"}
        )

        assert response.context["view"] == "pretty"

    def test_probe_sets_flatten_both_direct_and_nested_shapes(self, staff_client, active_config):
        response = staff_client.get(reverse("web_ui:config-detail", args=[active_config.pk]))

        rows = {
            (row["organism"], row["library_prep"]): row["probe_set"]
            for row in response.context["probe_set_rows"]
        }
        assert rows[("mouse", "10xV4_FX16")] == "mouse_probe_set"
        assert rows[("human", "All")] == "human_probe_set"

    def test_a_modality_with_no_post_alignment_commands_says_so(self, staff_client, active_config):
        """The fixture's RTX workflow has an empty post_alignment_command_configs list."""
        response = staff_client.get(reverse("web_ui:config-detail", args=[active_config.pk]))

        assert b"This config defines no post-alignment commands for RTX." in response.content

    def test_every_modality_and_stage_is_in_the_response_for_client_side_tabs(
        self, staff_client, active_config
    ):
        """Modality/stage switch client-side (tabs.js), not via a page reload, so every
        combination has to already be in the markup for the browser to show on click."""
        response = staff_client.get(reverse("web_ui:config-detail", args=[active_config.pk]))
        text = response.content.decode()

        assert 'data-tab-panel="MTX"' in text
        assert 'data-tab-panel="RTX"' in text
        assert 'data-tab-group="config-stage-MTX"' in text
        assert 'data-tab-group="config-stage-RTX"' in text
        # ocs fastqs align tenx-arc (MTX alignment) and postalign tenx-arc (MTX post-alignment)
        assert b"ocs fastqs align tenx-arc" in response.content
        assert b"ocs fastqs postalign tenx-arc" in response.content

    def test_only_the_first_modality_starts_visible(self, staff_client, active_config):
        response = staff_client.get(reverse("web_ui:config-detail", args=[active_config.pk]))
        text = response.content.decode()

        mtx_panel = text.index('data-tab-panel="MTX"')
        rtx_panel = text.index('data-tab-panel="RTX"')
        assert "hidden" not in text[mtx_panel : mtx_panel + 60]
        assert "hidden" in text[rtx_panel : rtx_panel + 60]


class TestCart:
    def test_adds_selected_samples(self, logged_in, make_sample, user):
        make_sample("READY-1")
        make_sample("READY-2")

        response = logged_in.post(
            reverse("web_ui:cart-add"), {"fastq_names": ["READY-1", "READY-2"]}, follow=True
        )

        assert b"Added 2 samples to the cart" in response.content
        assert set(CartItem.objects.filter(user=user).values_list("sample__fastq_name", flat=True)) == {
            "READY-1",
            "READY-2",
        }

    def test_adding_twice_does_not_duplicate(self, logged_in, make_sample, user):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        response = logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]}, follow=True)

        assert b"1 already in the cart" in response.content
        assert CartItem.objects.filter(user=user).count() == 1

    def test_adding_nothing_is_refused(self, logged_in):
        response = logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": []}, follow=True)

        assert b"Select at least one sample" in response.content
        assert not CartItem.objects.exists()

    def test_a_repeated_add_cannot_duplicate_a_row(self, logged_in, make_sample, user):
        """Adding the same sample many times over leaves exactly one row."""
        make_sample("READY-1")

        for _ in range(5):
            logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1", "READY-1"]})

        assert CartItem.objects.filter(user=user, sample__fastq_name="READY-1").count() == 1

    def test_a_row_appearing_mid_request_is_not_an_error(self, logged_in, make_sample, user, monkeypatch):
        """A double-clicked button: the row lands between the read and the insert.

        Without ignore_conflicts the unique constraint turns the second request into a 500
        rather than the no-op it should be, so this simulates the race the read cannot see.
        """
        sample = make_sample("READY-1")
        import apps.web_ui.views.dashboard as dashboard_views

        real = dashboard_views._cart_sample_ids
        calls = {"n": 0}

        def racing(user_, samples):
            calls["n"] += 1
            if calls["n"] == 1:
                # The read says the cart is empty; another request fills it immediately after.
                CartItem.objects.create(user=user_, sample=sample)
                return set()
            return real(user_, samples)

        monkeypatch.setattr(dashboard_views, "_cart_sample_ids", racing)

        response = logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]}, follow=True)

        assert response.status_code == 200
        assert CartItem.objects.filter(user=user).count() == 1

    def test_a_sample_no_longer_in_the_mirror_is_reported(self, logged_in, make_sample):
        """A page open since before a re-sync can still list a sample that has since gone."""
        make_sample("READY-1")

        response = logged_in.post(
            reverse("web_ui:cart-add"), {"fastq_names": ["READY-1", "GONE-1"]}, follow=True
        )

        assert b"1 no longer in the mirror" in response.content


class TestCartAddFeedback:
    """The dashboard adds without leaving the page, so the answer has to come back as data.

    The button sits at the bottom of a table that scrolls inside its own box, which put the
    message banner most of a screen above it , adding to the cart read as nothing happening.
    """

    AJAX = {"headers": {"X-Requested-With": "XMLHttpRequest"}}

    def _post(self, client, names):
        return client.post(
            reverse("web_ui:cart-add"),
            {"fastq_names": names},
            headers={"x-requested-with": "XMLHttpRequest"},
        )

    def test_reports_what_it_added_and_the_new_total(self, logged_in, make_sample):
        make_sample("READY-1")
        make_sample("READY-2")

        body = self._post(logged_in, ["READY-1", "READY-2"]).json()

        assert body["added"] == 2
        assert body["already"] == 0
        assert body["cart_count"] == 2
        assert body["message"] == "Added 2 samples to the cart."

    def test_says_when_they_were_already_there(self, logged_in, make_sample):
        make_sample("READY-1")
        self._post(logged_in, ["READY-1"])

        body = self._post(logged_in, ["READY-1"]).json()

        assert body["added"] == 0
        assert body["already"] == 1
        assert body["cart_count"] == 1
        assert "already in the cart" in body["message"]

    def test_an_empty_selection_comes_back_as_an_error(self, logged_in):
        response = self._post(logged_in, [])

        assert response.status_code == 400
        assert "Select at least one sample" in response.json()["error"]

    def test_the_count_is_the_whole_cart_not_just_this_add(self, logged_in, make_sample):
        make_sample("READY-1")
        make_sample("READY-2")
        self._post(logged_in, ["READY-1"])

        body = self._post(logged_in, ["READY-2"]).json()

        assert body["added"] == 1
        assert body["cart_count"] == 2

    def test_without_the_header_it_still_redirects(self, logged_in, make_sample):
        """JavaScript off has to keep working , same counts, carried as messages."""
        make_sample("READY-1")

        response = logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        assert response.status_code == 302
        assert CartItem.objects.count() == 1

    def test_the_dashboard_has_somewhere_to_put_the_answer(self, logged_in, make_sample):
        make_sample("READY-1")

        content = logged_in.get(reverse("web_ui:dashboard")).content.decode()

        assert 'id="cart-feedback"' in content
        assert 'id="cart-count"' in content

    def test_the_nav_cart_badge_exists_even_when_empty_so_js_can_update_it(self, logged_in, make_sample):
        """The dashboard's JS writes this count in after an AJAX add; it can only do that
        if the element is already in the page, so it has to render at zero too."""
        content = logged_in.get(reverse("web_ui:dashboard")).content.decode()

        assert 'class="count d-none" id="nav-cart-badge"' in content
        assert 'id="nav-cart-count">0<' in content

    def test_the_nav_cart_badge_is_visible_once_something_is_in_the_cart(self, logged_in, make_sample):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        content = logged_in.get(reverse("web_ui:dashboard")).content.decode()

        assert 'class="count " id="nav-cart-badge"' in content
        assert 'id="nav-cart-count">1<' in content

    def test_carts_are_per_user(self, logged_in, client, make_sample, user, django_user_model):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        other = django_user_model.objects.create_user(username="other", password="password")
        client.force_login(other)

        assert CartItem.objects.filter(user=other).count() == 0
        assert b"Your cart is empty" in client.get(reverse("web_ui:checkout")).content

    def test_removes_selected(self, logged_in, make_sample, user):
        make_sample("READY-1")
        make_sample("READY-2")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1", "READY-2"]})

        logged_in.post(reverse("web_ui:cart-remove"), {"fastq_names": ["READY-1"]})

        assert list(CartItem.objects.filter(user=user).values_list("sample__fastq_name", flat=True)) == [
            "READY-2"
        ]

    def test_clears(self, logged_in, make_sample, user):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        logged_in.post(reverse("web_ui:cart-clear"))

        assert not CartItem.objects.filter(user=user).exists()


class TestCheckoutPage:
    def test_requires_login(self, client):
        response = client.get(reverse("web_ui:checkout"))

        assert response.status_code == 302
        assert "/accounts/login/" in response["Location"]

    def test_lists_the_cart(self, logged_in, make_sample):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        response = logged_in.get(reverse("web_ui:checkout"))

        assert b"READY-1" in response.content
        assert b"Review Submission" in response.content

    def test_paginates_cart_rows_with_the_shared_page_size_control(self, logged_in, make_sample):
        names = [f"READY-{number}" for number in range(60)]
        for name in names:
            make_sample(name)
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": names})

        response = logged_in.get(reverse("web_ui:checkout"), {"checkout_page_size": 25})

        content = response.content.decode()
        assert "1–25" in content
        assert "of 60" in content
        assert 'name="fastq_names" value="READY-0"' in content
        assert (
            'class="form-check-input select-cart-sample"\n                       value="READY-59"'
            not in content
        )
        assert "checkout_page=2" in content

    def test_keeps_deselected_samples_out_of_submission_hidden_fields(self, logged_in, make_sample):
        make_sample("READY-1")
        make_sample("READY-2")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1", "READY-2"]})

        response = logged_in.get(reverse("web_ui:checkout"), {"exclude_fastq_names": ["READY-1"]})

        assert response.context["checkout_selected_fastq_names"] == ["READY-2"]

    def test_says_when_no_config_has_been_uploaded(self, logged_in, make_sample):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        response = logged_in.get(reverse("web_ui:checkout"))

        assert b"No config has been uploaded yet" in response.content

    def test_shows_only_the_columns_the_command_is_built_from(self, logged_in, make_sample):
        """The cart is not column-configurable; it shows what a submission decision needs."""
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        content = logged_in.get(reverse("web_ui:checkout")).content.decode()
        header = content.split('id="cart-table"', 1)[1].split("</thead>", 1)[0]

        for label in (
            "Fastq Name",
            "Study Set",
            "Load Name",
            "Batch Name From Vendor",
            "Workflow",
            "Organism",
            "Library Prep Method",
            "Ingest",
            "Alignment",
            "Post-alignment",
        ):
            assert label in header

    def test_does_not_show_the_dashboards_extra_columns(self, logged_in, user, make_sample):
        """A column turned on to chase a problem last week must not follow you here."""
        user.visible_columns = ["fastq_name", "cell_capture", "sample_type", "demand:align"]
        user.save(update_fields=["visible_columns"])
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        content = logged_in.get(reverse("web_ui:checkout")).content.decode()
        header = content.split('id="cart-table"', 1)[1].split("</thead>", 1)[0]

        assert "Cell Capture" not in header
        assert "Sample Type" not in header
        assert "Demand ID" not in header
        # Still the fixed set, not whatever the user chose.
        assert "Load Name" in header

    def test_offers_the_uploaded_configs(self, logged_in, active_config, make_sample):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        response = logged_in.get(reverse("web_ui:checkout"))

        assert b"Config driving this submission" in response.content
        assert b"config.jsonc" in response.content
        assert b"(active)" not in response.content
        assert b"(uploaded " in response.content


class TestConfigDrivesTheSubmission:
    """The config prefills the command , that is the whole point of choosing one."""

    def test_infers_the_stage_from_the_samples_own_status(self, logged_in, active_config, make_sample):
        """One ready to align, one already aligned. Neither was told which stage to run."""
        make_sample("TO-ALIGN")
        make_sample("TO-QC", align="COMPLETED")

        response = logged_in.post(reverse("web_ui:submit-commands"), {"fastq_names": ["TO-ALIGN", "TO-QC"]})

        content = response.content.decode()
        assert "ocs fastqs align tenx-arc" in content
        assert "ocs fastqs postalign tenx-arc" in content

    def test_fills_the_reference_from_organism_and_modality(self, logged_in, active_config, make_sample):
        make_sample("MOUSE-1", organism_common_name="mouse")

        response = logged_in.post(reverse("web_ui:submit-commands"), {"fastq_names": ["MOUSE-1"]})

        assert b"mouse_mtx_ref" in response.content

    def test_fills_the_chemistry_from_the_library_prep(self, logged_in, active_config, make_sample):
        make_sample(
            "RTX-1",
            batch_name_from_vendor="RTX-1",
            library_prep_method_name="10xV4",
            organism_common_name="mouse",
        )

        response = logged_in.post(reverse("web_ui:submit-commands"), {"fastq_names": ["RTX-1"]})

        assert b"--chemistry SC3Pv4" in response.content

    def test_an_inactive_config_can_be_previewed_without_activating_it(
        self, logged_in, active_config, config, user, make_sample
    ):
        """Picking a config on the checkout page builds against it, not the active one."""
        other = dict(config)
        other["references"] = {**config["references"], "mouse": {"MTX": "OTHER_REF", "RTX": "x"}}
        inactive = WorkflowConfig.objects.create(
            name="candidate.jsonc", raw="{}", data=other, uploaded_by=user
        )
        make_sample("MOUSE-1")

        response = logged_in.post(
            reverse("web_ui:submit-commands"), {"fastq_names": ["MOUSE-1"], "config_id": str(inactive.pk)}
        )

        assert b"OTHER_REF" in response.content
        assert b"mouse_mtx_ref" not in response.content

    def test_skips_a_sample_whose_ingest_has_not_finished(self, logged_in, active_config, make_sample):
        make_sample("WAITING-1", ingest=NOT_COMPLETED)

        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["WAITING-1"]})

        assert b"ingest_incomplete" in response.content


class TestSubmitModalRenders:
    """The modal's own controls, since a template that half-renders still returns 200."""

    def test_groups_commands_by_vendor_batch(self, logged_in, active_config, make_sample):
        make_sample("A-1", batch_name_from_vendor="MTX-22068")
        make_sample("B-1", batch_name_from_vendor="MTX-22069")

        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["A-1", "B-1"]})

        content = response.content.decode()
        assert "MTX-22068" in content
        assert "MTX-22069" in content
        assert content.count("Show/Hide") == 2

    def test_each_command_has_an_editor(self, logged_in, active_config, make_sample):
        make_sample("MOUSE-1")

        content = logged_in.post(
            reverse("web_ui:submit-review"), {"fastq_names": ["MOUSE-1"]}
        ).content.decode()

        assert 'name="override__MOUSE-1__command_config"' in content
        assert 'name="override__MOUSE-1__reference_name"' in content
        assert 'name="override__MOUSE-1__command"' in content
        assert "Reset to config" in content

    def test_the_editor_offers_only_fields_the_command_actually_uses(
        self, logged_in, active_config, make_sample
    ):
        """A menu that cannot change the command it sits under is not a choice.

        The MTX alignment command substitutes {reference_name} but never {chemistry}, so a
        Chemistry menu above it would have been decoration , the value had nowhere to go.
        """
        make_sample("MOUSE-1")

        content = logged_in.post(
            reverse("web_ui:submit-review"), {"fastq_names": ["MOUSE-1"]}
        ).content.decode()

        assert 'name="override__MOUSE-1__reference_name"' in content
        assert 'name="override__MOUSE-1__chemistry"' not in content

    def test_a_command_that_uses_chemistry_is_offered_it(self, logged_in, active_config, make_sample):
        """The RTX alignment command does substitute {chemistry}, so the menu belongs."""
        make_sample("RTX-1", batch_name_from_vendor="RTX-900", library_prep_method_name="10xV4")

        content = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["RTX-1"]}).content.decode()

        assert 'name="override__RTX-1__chemistry"' in content
        assert 'name="override__RTX-1__reference_name"' in content

    def test_the_reference_menu_offers_only_this_organisms_references(
        self, logged_in, active_config, make_sample
    ):
        """A mouse sample must not be offerable against the human reference."""
        make_sample("MOUSE-1", organism_common_name="mouse")

        content = logged_in.post(
            reverse("web_ui:submit-review"), {"fastq_names": ["MOUSE-1"]}
        ).content.decode()

        assert "mouse_mtx_ref" in content
        assert "human_all_ref" not in content

    def test_edits_survive_the_step_to_the_confirmation_modal(self, logged_in, active_config, make_sample):
        """The confirmation modal renders commands as text, so it must re-post the edits."""
        make_sample("MOUSE-1")

        content = logged_in.post(
            reverse("web_ui:submit-commands"),
            {"fastq_names": ["MOUSE-1"], "override__MOUSE-1__reference_name": "mouse_rtx_ref"},
        ).content.decode()

        assert 'name="override__MOUSE-1__reference_name" value="mouse_rtx_ref"' in content


class TestUntouchedCommandDoesNotOutrankTheMenus:
    """The editor posts its textarea whether or not anybody typed in it.

    A hand-edited command outranks the menus, so an untouched textarea used to outrank a
        reference the user chose, changing Reference did not update the command.
    The rendered command is posted alongside it so the two cases can be told apart.
    """

    def _rendered_command(self, logged_in, fastq_name, **extra):
        response = logged_in.post(reverse("web_ui:submit-commands"), {"fastq_names": [fastq_name], **extra})
        return re.search(rb"ocs fastqs align[^<]*", response.content).group().decode().strip()

    def test_a_changed_menu_wins_when_the_textarea_was_not_touched(
        self, logged_in, active_config, make_sample
    ):
        make_sample("MOUSE-1")
        rendered = self._rendered_command(logged_in, "MOUSE-1")

        logged_in.post(
            reverse("web_ui:submit-confirm"),
            {
                "fastq_names": ["MOUSE-1"],
                "override__MOUSE-1__reference_name": "mouse_rtx_ref",
                # Exactly what the browser posts: the textarea, carrying what was rendered.
                "override__MOUSE-1__command": rendered,
                "override__MOUSE-1__command_original": rendered,
            },
        )

        assert "mouse_rtx_ref" in QueueEntry.objects.get().command

    def test_a_typed_command_still_wins_over_the_menus(self, logged_in, active_config, make_sample):
        """The other half of the rule: a real edit is still submitted verbatim."""
        make_sample("MOUSE-1")
        rendered = self._rendered_command(logged_in, "MOUSE-1")
        typed = "ocs fastqs align tenx-arc --load-names TYPED_BY_HAND"

        logged_in.post(
            reverse("web_ui:submit-confirm"),
            {
                "fastq_names": ["MOUSE-1"],
                "override__MOUSE-1__reference_name": "mouse_rtx_ref",
                "override__MOUSE-1__command": typed,
                "override__MOUSE-1__command_original": rendered,
            },
        )

        assert QueueEntry.objects.get().command == typed

    def test_whitespace_alone_does_not_count_as_an_edit(self, logged_in, active_config, make_sample):
        """A textarea round-trips with a trailing newline in some browsers."""
        make_sample("MOUSE-1")
        rendered = self._rendered_command(logged_in, "MOUSE-1")

        logged_in.post(
            reverse("web_ui:submit-confirm"),
            {
                "fastq_names": ["MOUSE-1"],
                "override__MOUSE-1__reference_name": "mouse_rtx_ref",
                "override__MOUSE-1__command": f"\n  {rendered}  \n",
                "override__MOUSE-1__command_original": rendered,
            },
        )

        assert "mouse_rtx_ref" in QueueEntry.objects.get().command

    def test_the_editor_carries_what_the_live_rebuild_needs(self, logged_in, active_config, make_sample):
        """The markup the view and the rebuild both depend on, or neither works."""
        make_sample("MOUSE-1")

        content = logged_in.post(
            reverse("web_ui:submit-review"), {"fastq_names": ["MOUSE-1"]}
        ).content.decode()

        assert 'name="override__MOUSE-1__command_original"' in content
        # The rebuild finds the editor and the row it writes back into by these.
        assert 'data-fastq="MOUSE-1"' in content
        assert "command-editor" in content
        assert "Reset to config" in content


class TestCommandPreview:
    """The live rebuild behind the editor's menus.

    It replaced an Apply button that re-posted the whole form: a full page render, and every
    open editor closing, to change one field.
    """

    def test_rebuilds_the_command_for_one_sample(self, logged_in, active_config, make_sample):
        make_sample("MOUSE-1")

        response = logged_in.post(
            reverse("web_ui:command-preview"),
            {
                "fastq_name": "MOUSE-1",
                "fastq_names": ["MOUSE-1"],
                "override__MOUSE-1__reference_name": "mouse_rtx_ref",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "mouse_rtx_ref" in body["command"]
        assert body["command_config"] == "default"
        assert body["spacing"] == 180
        assert body["edited"] is False

    def test_switching_the_command_config_rebuilds_from_it(self, logged_in, active_config, make_sample):
        make_sample("TO-QC", align="COMPLETED")

        body = logged_in.post(
            reverse("web_ui:command-preview"), {"fastq_name": "TO-QC", "fastq_names": ["TO-QC"]}
        ).json()

        assert "ocs fastqs postalign tenx-arc" in body["command"]

    def test_a_multiome_half_previews_against_its_partner(self, logged_in, active_config, make_sample):
        """Planned alone it would report pair_missing, which is not the command it will get."""
        make_sample("GEX-1", library_prep_method_name="10xMultX_GEX", load_name="L1")
        make_sample("ATAC-1", library_prep_method_name="10xMultX_ATAC", load_name="L1")

        response = logged_in.post(
            reverse("web_ui:command-preview"), {"fastq_name": "GEX-1", "fastq_names": ["GEX-1"]}
        )

        assert response.status_code == 200
        assert "ocs fastqs align tenx-arc" in response.json()["command"]

    def test_a_sample_with_nothing_to_run_says_why(self, logged_in, active_config, make_sample):
        make_sample("WAITING-1", ingest=NOT_COMPLETED)

        response = logged_in.post(
            reverse("web_ui:command-preview"), {"fastq_name": "WAITING-1", "fastq_names": ["WAITING-1"]}
        )

        assert response.status_code == 409
        assert response.json()["reason"] == "ingest_incomplete"

    def test_an_unknown_sample_is_a_404(self, logged_in, active_config):
        response = logged_in.post(reverse("web_ui:command-preview"), {"fastq_name": "NOPE"})

        assert response.status_code == 404

    def test_it_requires_login(self, client, make_sample):
        make_sample("MOUSE-1")

        response = client.post(reverse("web_ui:command-preview"), {"fastq_name": "MOUSE-1"})

        assert response.status_code == 302

    def test_it_writes_nothing(self, logged_in, active_config, make_sample):
        """A preview that queued something would be a submission nobody confirmed."""
        make_sample("MOUSE-1")

        logged_in.post(
            reverse("web_ui:command-preview"), {"fastq_name": "MOUSE-1", "fastq_names": ["MOUSE-1"]}
        )

        assert not QueueEntry.objects.exists()


class TestCommandEditing:
    """Switching and filling in commands, the way the old app's modal allowed."""

    def test_switching_the_reference_changes_the_command(self, logged_in, active_config, make_sample):
        make_sample("MOUSE-1")

        response = logged_in.post(
            reverse("web_ui:submit-commands"),
            {"fastq_names": ["MOUSE-1"], "override__MOUSE-1__reference_name": "mouse_rtx_ref"},
        )

        assert b"mouse_rtx_ref" in response.content

    def test_a_hand_edited_command_is_what_gets_queued(self, logged_in, active_config, make_sample):
        make_sample("MOUSE-1")

        logged_in.post(
            reverse("web_ui:submit-confirm"),
            {
                "fastq_names": ["MOUSE-1"],
                "override__MOUSE-1__command": "ocs fastqs align tenx-arc --load-names EDITED",
            },
        )

        entry = QueueEntry.objects.get()
        assert entry.command == "ocs fastqs align tenx-arc --load-names EDITED"
        assert entry.command_args == ["ocs", "fastqs", "align", "tenx-arc", "--load-names", "EDITED"]

    def test_a_quoted_value_survives_editing_as_one_argument(self, logged_in, active_config, make_sample):
        """The CLI runs without a shell, so quotes must be consumed here, not passed on."""
        make_sample("MOUSE-1")

        logged_in.post(
            reverse("web_ui:submit-confirm"),
            {
                "fastq_names": ["MOUSE-1"],
                "override__MOUSE-1__command": 'ocs fastqs align tenx-arc --load-names "A B"',
            },
        )

        assert QueueEntry.objects.get().command_args[-1] == "A B"

    def test_an_untouched_sample_plans_the_same_with_overrides_posted(
        self, logged_in, active_config, make_sample
    ):
        make_sample("MOUSE-1")
        make_sample("MOUSE-2")

        logged_in.post(
            reverse("web_ui:submit-confirm"),
            {
                "fastq_names": ["MOUSE-1", "MOUSE-2"],
                "override__MOUSE-1__reference_name": "mouse_rtx_ref",
            },
        )

        untouched = QueueEntry.objects.get(sample__fastq_name="MOUSE-2")
        assert "mouse_mtx_ref" in untouched.command


class TestCheckoutClearsTheCart:
    def test_queued_samples_leave_the_cart(self, logged_in, active_config, make_sample, user):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        logged_in.post(reverse("web_ui:submit-confirm"), {"fastq_names": ["READY-1"]})

        assert QueueEntry.objects.count() == 1
        assert not CartItem.objects.filter(user=user).exists()

    def test_a_skipped_sample_stays_staged(self, logged_in, active_config, make_sample, user):
        """It could not be submitted yet; it should still be there when it can be."""
        make_sample("WAITING-1", ingest=NOT_COMPLETED)
        logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["WAITING-1"]})

        logged_in.post(reverse("web_ui:submit-confirm"), {"fastq_names": ["WAITING-1"]})

        assert not QueueEntry.objects.exists()
        assert CartItem.objects.filter(user=user, sample__fastq_name="WAITING-1").exists()


class TestMissingValueIsAskedFor:
    """The modal asks for a value the config cannot supply, rather than sending it empty."""

    @pytest.fixture
    def flex_config(self, config, user):
        config["workflows"]["RTX"]["alignment_command_configs"].append(
            {
                "name": "10xV4_FX4",
                "match": {"library_preps": ["10xV4_FX4"]},
                "command": ["ocs", "fastqs", "align", "tenx-rnaseq-multi"],
                "arguments": [
                    {"flag": "--reference-names", "value": "{reference_name}"},
                    {"flag": "--cellflex-probe-set-name", "value": "{probe_set}"},
                ],
                "spacing": 180,
            }
        )
        return WorkflowConfig.objects.create(
            name="flex.jsonc", raw="{}", data=config, uploaded_by=user, is_active=True
        )

    def test_the_modal_asks_for_the_missing_value(self, logged_in, flex_config, make_sample):
        make_sample(
            "NEW-1",
            batch_name_from_vendor="RTX-900",
            library_prep_method_name="10xV5_NEW",
            organism_common_name="mouse",
        )

        content = logged_in.post(
            reverse("web_ui:submit-review"),
            {
                "fastq_names": ["NEW-1"],
                "command_config_choice": "align::10xV5_NEW::10xV4_FX4",
            },
        ).content.decode()

        assert 'name="missing__align__10xV5_NEW__probe_set"' in content
        assert "Needs a value" in content

    def test_the_answer_builds_the_command(self, logged_in, flex_config, make_sample):
        make_sample(
            "NEW-1",
            batch_name_from_vendor="RTX-900",
            library_prep_method_name="10xV5_NEW",
            organism_common_name="mouse",
        )

        content = logged_in.post(
            reverse("web_ui:submit-review"),
            {
                "fastq_names": ["NEW-1"],
                "command_config_choice": "align::10xV5_NEW::10xV4_FX4",
                "missing__align__10xV5_NEW__probe_set": "mouse_custom_probe_set",
            },
        ).content.decode()

        assert "--cellflex-probe-set-name mouse_custom_probe_set" in content
        assert 'name="missing__align__10xV5_NEW__probe_set"' not in content


class TestMenuChangeWithUntouchedTextarea:
    """Changing a menu must not be discarded by the command textarea nobody touched.

    The editor posts both: the menus, and the raw command textarea holding whatever it was
    rendered with. Deciding "was this edited?" by comparing the textarea against the command
    the menus would build *now* cannot tell the two apart , changing a menu is precisely
    what makes them differ , so an untouched textarea looked edited and its stale text won.
    """

    def _rendered_command(self, response) -> str:
        return re.search(rb"ocs fastqs align[^<]*", response.content).group().decode().strip()

    def test_a_menu_change_survives_an_untouched_textarea(self, logged_in, active_config, make_sample):
        make_sample("MOUSE-1")
        rendered = self._rendered_command(
            logged_in.post(reverse("web_ui:submit-commands"), {"fastq_names": ["MOUSE-1"]})
        )

        logged_in.post(
            reverse("web_ui:submit-confirm"),
            {
                "fastq_names": ["MOUSE-1"],
                "override__MOUSE-1__reference_name": "mouse_rtx_ref",
                # What the browser posts for a field the user never touched.
                "override__MOUSE-1__command": rendered,
                "override__MOUSE-1__command_original": rendered,
            },
        )

        queued = QueueEntry.objects.get()
        assert "mouse_rtx_ref" in queued.command, "the reference menu was silently ignored"
        assert "mouse_mtx_ref" not in queued.command

    def test_a_hand_edited_command_still_wins(self, logged_in, active_config, make_sample):
        """The raw textarea is the last escape hatch and must keep overriding the menus."""
        make_sample("MOUSE-1")
        rendered = self._rendered_command(
            logged_in.post(reverse("web_ui:submit-commands"), {"fastq_names": ["MOUSE-1"]})
        )
        by_hand = f"{rendered} --extra-flag"

        logged_in.post(
            reverse("web_ui:submit-confirm"),
            {
                "fastq_names": ["MOUSE-1"],
                "override__MOUSE-1__reference_name": "mouse_rtx_ref",
                "override__MOUSE-1__command": by_hand,
                "override__MOUSE-1__command_original": rendered,
            },
        )

        queued = QueueEntry.objects.get()
        assert queued.command == by_hand


class TestBackFromConfirm:
    """The confirmation step can go back to the editor without losing what was chosen."""

    def test_back_returns_to_the_command_step(self, logged_in, active_config, make_sample):
        make_sample("MOUSE-1")

        content = logged_in.post(
            reverse("web_ui:submit-commands"), {"fastq_names": ["MOUSE-1"]}
        ).content.decode()

        assert 'id="back-to-review"' in content
        assert reverse("web_ui:submit-review") in content
        assert "formnovalidate" in content

    def test_going_back_keeps_the_edits_made_so_far(self, logged_in, active_config, make_sample):
        """Back must carry the submission forward, not re-plan it from the config.

        Someone who reads a command on the confirm step and wants a different reference
        needs the editor with their choices intact; landing on a freshly planned step 1
        would silently discard them.
        """
        make_sample("MOUSE-1")

        response = logged_in.post(
            reverse("web_ui:submit-review"),
            {
                "fastq_names": ["MOUSE-1"],
                "override__MOUSE-1__reference_name": "mouse_rtx_ref",
                "email": "someone@alleninstitute.org",
            },
        )

        assert response.context["open_modal"] == "submit"
        assert response.context["submission"]["overrides"]["MOUSE-1"] == {"reference_name": "mouse_rtx_ref"}
        assert b"mouse_rtx_ref" in response.content


class TestDiscardWarning:
    """Closing a submission modal warns only when there is something to lose."""

    def test_no_warning_when_nothing_has_been_chosen(self, logged_in, active_config, make_sample):
        """A prompt on every close is one people learn to dismiss without reading."""
        make_sample("MOUSE-1")

        response = logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": ["MOUSE-1"]})

        assert response.context["has_unsaved_choices"] is False
        # The bare string also appears in base.html's selector, so assert the attribute.
        assert b'data-has-edits="true"' not in response.content

    def test_a_per_sample_edit_arms_the_warning(self, logged_in, active_config, make_sample):
        make_sample("MOUSE-1")

        response = logged_in.post(
            reverse("web_ui:submit-review"),
            {
                "fastq_names": ["MOUSE-1"],
                "override__MOUSE-1__reference_name": "mouse_rtx_ref",
            },
        )

        assert response.context["has_unsaved_choices"] is True
        assert b'data-has-edits="true"' in response.content

    def test_a_chosen_workflow_arms_the_warning(self, logged_in, active_config, make_sample):
        make_sample("MOUSE-1")

        response = logged_in.post(
            reverse("web_ui:submit-review"), {"fastq_names": ["MOUSE-1"], "modality": "MTX"}
        )

        assert response.context["has_unsaved_choices"] is True

    def test_the_warning_covers_every_way_out_not_just_cancel(self):
        """Bound to the modal's hide event, so Escape and the close cross are covered too."""
        base = (TEMPLATES / "base.html").read_text()

        assert 'querySelectorAll(".modal[data-has-edits]")' in base
        assert 'addEventListener("hide.bs.modal"' in base
        assert "data-bs-dismiss" not in base.split("hide.bs.modal")[1][:400]

    def test_the_confirmation_is_in_page_not_a_browser_dialog(self, logged_in, active_config, make_sample):
        make_sample("MOUSE-1")

        content = logged_in.post(
            reverse("web_ui:submit-review"),
            {"fastq_names": ["MOUSE-1"], "override__MOUSE-1__reference_name": "mouse_rtx_ref"},
        ).content.decode()

        assert 'role="alertdialog"' in content
        assert 'data-discard="keep"' in content
        assert 'data-discard="confirm"' in content
        assert "window.confirm" not in content, "the browser dialog should be gone"

    def test_the_sheet_is_labelled_and_starts_hidden(self, logged_in, active_config, make_sample):
        """A dialog with no accessible name announces as an unlabelled group."""
        make_sample("MOUSE-1")

        content = logged_in.post(
            reverse("web_ui:submit-review"),
            {"fastq_names": ["MOUSE-1"], "override__MOUSE-1__reference_name": "mouse_rtx_ref"},
        ).content.decode()

        assert 'id="submit-discard"' in content
        assert 'aria-labelledby="submit-discard-title"' in content
        assert 'aria-describedby="submit-discard-body"' in content
        assert re.search(r'class="discard-confirm"[^>]*\bhidden\b', content)

    def test_the_submission_behind_the_sheet_is_made_inert(self):
        """Without inert, Tab walks out of the question and into the form it asks about."""
        base = (TEMPLATES / "base.html").read_text()

        assert "form.inert = true" in base
        assert "form.inert = false" in base

    def test_escape_while_the_sheet_is_open_keeps_editing(self):
        """Escape must not fall through to Bootstrap and close everything."""
        base = (TEMPLATES / "base.html").read_text()
        handler = base.split('event.key !== "Escape"')[1][:400]

        assert "stopPropagation" in handler
        assert "close()" in handler
