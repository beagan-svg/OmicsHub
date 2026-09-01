"""Workflow config upload, activation, settings, and config detail pages."""

from __future__ import annotations

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.workflow_engine.models import WorkflowConfig

from .conftest import messages_in

pytestmark = pytest.mark.django_db


def config_upload(data: dict, name: str = "config.jsonc") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, json.dumps(data).encode(), content_type="application/json")


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
