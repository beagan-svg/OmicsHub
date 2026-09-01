"""Command customization: menus, previews, overrides, and the discard-changes warning."""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

from apps.sample_catalog.models import NOT_COMPLETED
from apps.submission_queue.models import QueueEntry
from apps.workflow_engine.models import WorkflowConfig

from .conftest import TEMPLATES

pytestmark = pytest.mark.django_db


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

    def test_groups_commands_by_batch_name_from_vendor(self, logged_in, active_config, make_sample):
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
