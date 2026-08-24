"""The pages, data downloads, and the three-step submission the dashboard exists for."""

from __future__ import annotations

import io
import zipfile
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.sample_catalog.models import NOT_COMPLETED, Stage, StageStatus
from apps.submission_queue.models import QueueEntry
from apps.web_ui import columns

pytestmark = pytest.mark.django_db


@pytest.fixture
def queued(logged_in, active_config, make_sample):
    """Run the whole submission flow and return the resulting entry."""

    def _queue(fastq_name="READY-1", **sample_kwargs):
        make_sample(fastq_name, **sample_kwargs)
        logged_in.post(reverse("web_ui:submit-confirm"), {"fastq_names": [fastq_name]})
        return QueueEntry.objects.get(sample__fastq_name=fastq_name)

    return _queue


class TestAccess:
    @pytest.mark.parametrize(
        "name",
        [
            "web_ui:dashboard",
            "web_ui:data-locations",
            "web_ui:queue",
            "web_ui:job-monitor",
            "web_ui:failed",
            "web_ui:configs",
        ],
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
        assert logged_in.get(reverse("web_ui:configs")).status_code == 403


class TestDashboard:
    def test_page_size_changes_the_number_of_rows(self, logged_in, make_sample):
        for index in range(55):
            make_sample(f"NW-PAGE-{index:03d}")

        response = logged_in.get(reverse("web_ui:dashboard"), {"page_size": "25"})

        assert response.context["page"].paginator.per_page == 25
        assert len(response.context["page"].object_list) == 25

    def test_lists_samples_with_stage_status(self, logged_in, make_sample):
        make_sample("READY-1", align="IN_PROGRESS")

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert b"READY-1" in response.content
        assert b"IN_PROGRESS" in response.content

    def test_live_status_returns_only_requested_sample_stage_data(self, logged_in, make_sample):
        sample = make_sample("LIVE-1")
        sample.stage_statuses.create(
            stage=Stage.ALIGN,
            status="IN_PROGRESS",
            demand_id="live-demand",
            file_store_id="live-store",
        )
        other = make_sample("LIVE-2")
        other.stage_statuses.create(stage=Stage.ALIGN, status="COMPLETED", demand_id="other-demand")

        response = logged_in.get(
            reverse("web_ui:live-status"), {"fastq_names": [sample.fastq_name, "MISSING"]}
        )

        assert response.json()["rows"]["LIVE-1"]["align"] == {
            "status": "IN_PROGRESS",
        }
        assert "LIVE-2" not in response.json()["rows"]

    def test_live_status_ignores_requests_for_too_many_samples(self, logged_in):
        response = logged_in.get(
            reverse("web_ui:live-status"), {"fastq_names": [f"LIVE-{i}" for i in range(201)]}
        )

        assert response.json() == {"rows": {}}

    def test_shows_the_inferred_workflow(self, logged_in, active_config, make_sample):
        make_sample("READY-1", batch_name_from_vendor="MTX-22068")

        assert b"MTX" in logged_in.get(reverse("web_ui:dashboard")).content

    def test_an_unrecognised_prefix_shows_as_rtx(self, logged_in, active_config, make_sample):
        """Modality is a stored column now, and an unknown batch prefix defaults to RTX,
        so no row on the dashboard is left without a workflow."""
        sample = make_sample("ODD-1", batch_name_from_vendor="ZZZ-1")

        assert sample.modality == "RTX"
        assert b"ODD-1" in logged_in.get(reverse("web_ui:dashboard")).content

    def test_filter_options_are_not_repeated(self, logged_in, make_sample):
        """Meta.ordering leaking into DISTINCT repeats every option once per sample."""
        make_sample("A-1", batch_name_from_vendor="MTX-22068")
        make_sample("A-2", batch_name_from_vendor="MTX-22068")

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.context["organisms"] == ["mouse"]
        assert response.context["batches"] == ["MTX-22068"]

    def test_shows_the_default_columns(self, logged_in, make_sample):
        make_sample("READY-1")

        response = logged_in.get(reverse("web_ui:dashboard"))

        # Asserted on the rendered column set rather than the page, because every label
        # also appears in the column-picker menu.
        keys = [column.key for column in response.context["columns"]]
        assert "library_prep_method_name" in keys
        assert "sequencing_vendor" not in keys

    def test_choosing_columns_changes_the_table(self, logged_in, make_sample, user):
        make_sample("READY-1")

        logged_in.post(reverse("web_ui:set-columns"), {"columns": ["fastq_name", "sequencing_vendor"]})

        response = logged_in.get(reverse("web_ui:dashboard"))
        user.refresh_from_db()
        assert user.visible_columns == ["fastq_name", "sequencing_vendor"]
        assert [column.key for column in response.context["columns"]] == [
            "fastq_name",
            "sequencing_vendor",
        ]

    def test_fastq_name_cannot_be_hidden(self, logged_in, make_sample, user):
        """Hiding the identifying column leaves a table nobody can read."""
        make_sample("READY-1")

        logged_in.post(reverse("web_ui:set-columns"), {"columns": ["organism_common_name"]})

        user.refresh_from_db()
        assert user.visible_columns[0] == "fastq_name"

    def test_column_choices_survive_a_new_session(self, logged_in, make_sample, client, user):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:set-columns"), {"columns": ["fastq_name", "sample_type"]})

        client.force_login(user)

        assert b"Sample Type" in client.get(reverse("web_ui:dashboard")).content

    def test_the_column_menu_offers_every_column_exactly_once(self, logged_in, make_sample):
        """The chooser is built from sections now, and a column filed under no section , or
        under two , would silently vanish from it or appear twice."""
        make_sample("READY-1")

        response = logged_in.get(reverse("web_ui:dashboard"))

        grouped = [column.key for group in response.context["column_groups"] for column in group.columns]
        assert sorted(grouped) == sorted(column.key for column in columns.COLUMNS)

    def test_the_column_menu_offers_a_way_back_to_the_defaults(self, logged_in, make_sample):
        make_sample("READY-1")

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.context["default_column_keys"] == columns.DEFAULT_COLUMNS

    def test_filters_by_organism(self, logged_in, make_sample):
        make_sample("MOUSE-1", organism_common_name="mouse")
        make_sample("HUMAN-1", organism_common_name="human")

        response = logged_in.get(reverse("web_ui:dashboard"), {"organism_common_name": "human"})

        assert b"HUMAN-1" in response.content
        assert b"MOUSE-1" not in response.content

    def test_filters_by_stage_status(self, logged_in, make_sample):
        make_sample("DONE-1", align="COMPLETED")
        make_sample("TODO-1")

        response = logged_in.get(reverse("web_ui:dashboard"), {"align_status": "COMPLETED"})

        assert b"DONE-1" in response.content
        assert b"TODO-1" not in response.content

    def test_filters_by_a_stage_that_never_ran(self, logged_in, make_sample):
        make_sample("DONE-1", align="COMPLETED")
        make_sample("TODO-1")

        response = logged_in.get(reverse("web_ui:dashboard"), {"align_status": NOT_COMPLETED})

        assert b"TODO-1" in response.content
        assert b"DONE-1" not in response.content

    def test_filters_by_batch(self, logged_in, make_sample):
        make_sample("A-1", batch_name_from_vendor="MTX-22068")
        make_sample("B-1", batch_name_from_vendor="RTX-34056")

        response = logged_in.get(reverse("web_ui:dashboard"), {"batch_name_from_vendor": "MTX-22068"})

        assert b"A-1" in response.content
        assert b"B-1" not in response.content

    def test_multiple_advanced_filters_work_on_both_dashboards(self, logged_in, make_sample):
        make_sample(
            "A-1",
            batch_name_from_vendor="MTX-1",
            organism_common_name="mouse",
            library_prep_method_name="Prep-1",
        )
        make_sample(
            "B-1",
            batch_name_from_vendor="RTX-2",
            organism_common_name="human",
            library_prep_method_name="Prep-2",
        )
        make_sample(
            "C-1",
            batch_name_from_vendor="RFX-3",
            organism_common_name="rat",
            library_prep_method_name="Prep-3",
        )
        filters = [
            ("batch_name_from_vendor", "MTX-1"),
            ("batch_name_from_vendor", "RTX-2"),
            ("organism_common_name", "mouse"),
            ("organism_common_name", "human"),
            ("library_prep_method_name", "Prep-1"),
            ("library_prep_method_name", "Prep-2"),
        ]

        for page_name in ("dashboard", "data-locations"):
            response = logged_in.get(reverse(f"web_ui:{page_name}"), filters)
            assert {sample.fastq_name for sample in response.context["page"].object_list} == {"A-1", "B-1"}

    def test_searches_fastq_load_and_vendor_batch_names(self, logged_in, make_sample):
        make_sample("FASTQ-1", load_name="LOAD-1", batch_name_from_vendor="MTX-22068")
        make_sample("FASTQ-2", load_name="LOAD-2", batch_name_from_vendor="RTX-34056")

        response = logged_in.get(reverse("web_ui:dashboard"), {"fastq_name": "MTX-22068"})

        assert b"FASTQ-1" in response.content
        assert b"FASTQ-2" not in response.content

    def test_refresh_status_re_reads_the_posted_rows_from_ocs(self, logged_in, monkeypatch, make_sample):
        from apps.sample_catalog import ocs_sync as sync_service

        make_sample("A-1")
        make_sample("B-1")
        refreshed = []
        monkeypatch.setattr(
            sync_service,
            "sync_stage_statuses",
            lambda samples: refreshed.extend(sample.fastq_name for sample in samples),
        )

        response = logged_in.post(reverse("web_ui:refresh-status"), {"fastq_names": ["A-1"]}, follow=True)

        assert refreshed == ["A-1"]
        assert b"Refreshed status for 1 sample from OCS" in response.content

    def test_refresh_status_uses_the_submitted_table_row_count(self, logged_in, monkeypatch, make_sample):
        from apps.sample_catalog import ocs_sync as sync_service

        fastq_names = [f"REFRESH-{index:02d}" for index in range(55)]
        for fastq_name in fastq_names:
            make_sample(fastq_name)
        monkeypatch.setattr(sync_service, "sync_stage_statuses", lambda samples: None)

        response = logged_in.post(reverse("web_ui:refresh-status"), {"fastq_names": fastq_names}, follow=True)

        assert b"Refreshed status for 55 samples from OCS" in response.content

    def test_refresh_status_survives_ocs_being_unreachable(self, logged_in, monkeypatch, make_sample):
        """The mirror is still readable; only the live read failed, and the table stays up."""
        from botocore.exceptions import EndpointConnectionError

        from apps.sample_catalog import ocs_sync as sync_service

        make_sample("A-1")

        def _boom(samples):
            raise EndpointConnectionError(endpoint_url="https://dynamodb.us-west-2.amazonaws.com")

        monkeypatch.setattr(sync_service, "sync_stage_statuses", _boom)

        response = logged_in.post(reverse("web_ui:refresh-status"), {"fastq_names": ["A-1"]}, follow=True)

        assert response.status_code == 200
        assert b"Could not reach OCS" in response.content

    def test_data_locations_uses_stage_file_store_rows(self, logged_in, monkeypatch, make_sample):
        sample = make_sample("A-1", align="COMPLETED")
        sample.stage_statuses.filter(stage=Stage.ALIGN).update(file_store_id="store-1")
        monkeypatch.setattr(
            "apps.web_ui.data_location_queries.dynamodb.get_file_stores",
            lambda ids: {"store-1": {"file_store_id": "store-1", "s3_uri": "s3://bucket/results"}},
        )

        response = logged_in.get(reverse("web_ui:data-locations"), {"fastq_name": "A-1"})

        assert response.status_code == 200
        assert b"s3://bucket/results" in response.content
        assert b"store-1" not in response.content
        assert b"demand-align" not in response.content

    def test_data_locations_uses_sample_filters_and_default_fields(self, logged_in, make_sample):
        make_sample("A-1", batch_name_from_vendor="MTX-10", organism_common_name="mouse")
        make_sample("B-1", batch_name_from_vendor="RTX-20", organism_common_name="human")

        response = logged_in.get(
            reverse("web_ui:data-locations"),
            {"study": "StudyA", "organism_common_name": "mouse", "batch_prefix": "MTX"},
        )

        assert [sample.fastq_name for sample in response.context["page"].object_list] == ["A-1"]
        assert b"Study Set" in response.content
        assert b"Batch Name From Vendor" in response.content
        assert b"Library Prep Method" in response.content
        assert "studies" in [column.key for column in response.context["all_columns"]]
        assert b"More Filters" in response.content

    def test_data_locations_filters_by_multiple_studies(self, logged_in, make_sample):
        for fastq_name, study in (("A-1", "StudyA"), ("B-1", "StudyB"), ("C-1", "StudyC")):
            sample = make_sample(fastq_name)
            sample.studies = [study]
            sample.save(update_fields=["studies"])

        response = logged_in.get(
            reverse("web_ui:data-locations"),
            [("study", "StudyA"), ("study", "StudyB")],
        )

        assert {sample.fastq_name for sample in response.context["page"].object_list} == {"A-1", "B-1"}

    def test_data_locations_uses_the_shared_column_settings(self, logged_in, make_sample):
        make_sample("A-1")

        logged_in.post(
            reverse("web_ui:set-columns"),
            {"scope": "locations", "columns": ["load_name", "organism_common_name"]},
        )

        response = logged_in.get(reverse("web_ui:data-locations"))

        assert [column.key for column in response.context["columns"]] == [
            "load_name",
            "organism_common_name",
        ]

    def test_data_locations_can_show_one_stage(self, logged_in, make_sample):
        make_sample("A-1")

        response = logged_in.get(reverse("web_ui:data-locations"), {"location_stage": "align"})

        assert response.context["selected_location_stage"] == "align"
        assert {row["stage"] for row in response.context["location_rows"]} == {Stage.ALIGN}
        assert all(row["show_selector"] for row in response.context["location_rows"])
        assert b'class="form-check-input select-location"' in response.content

    def test_data_locations_shows_batch_name_from_vendor(self, logged_in, make_sample):
        make_sample("A-1", batch_name_from_vendor="RFX-38026")

        response = logged_in.get(reverse("web_ui:data-locations"))

        assert "batch_name_from_vendor" in [column.key for column in response.context["columns"]]
        assert b"RFX-38026" in response.content

    def test_fastq_name_sorts_by_the_number_in_it_not_the_text(self, logged_in, make_sample):
        """Alphabetically "-10" comes before "-2" (the character '1' < '2'); the numbers
        they name go the other way. Names sharing every digit but the last one are exactly
        where a plain text sort gets it wrong."""
        make_sample("NY-MX22056-2")
        make_sample("NY-MX22056-9")
        make_sample("NY-MX22056-10")

        ascending = logged_in.get(reverse("web_ui:data-locations"), {"sort": "fastq_name", "dir": "asc"})
        descending = logged_in.get(reverse("web_ui:data-locations"), {"sort": "fastq_name", "dir": "desc"})

        def order(response):
            seen = []
            for row in response.context["location_rows"]:
                if row["fastq_name"] not in seen:
                    seen.append(row["fastq_name"])
            return seen

        assert order(ascending) == ["NY-MX22056-2", "NY-MX22056-9", "NY-MX22056-10"]
        assert order(descending) == ["NY-MX22056-10", "NY-MX22056-9", "NY-MX22056-2"]

    def test_fastq_name_header_is_a_sort_link(self, logged_in, make_sample):
        make_sample("A-1")

        response = logged_in.get(reverse("web_ui:data-locations"), {"sort": "fastq_name", "dir": "desc"})

        assert b'aria-sort="descending"' in response.content
        assert b"Sort by Fastq Name" in response.content

    def test_data_locations_empty_state_matches_the_dashboard_pattern(self, logged_in):
        """No samples in the mirror at all, so every filter combination is empty."""
        response = logged_in.get(reverse("web_ui:data-locations"))

        assert b"No samples match these filters." in response.content
        assert b"Clear filters" in response.content
        assert b"bi-search" in response.content

    def test_data_location_contents_loads_one_s3_folder(self, logged_in, monkeypatch, make_sample):
        sample = make_sample("A-1", align="COMPLETED")
        StageStatus.objects.filter(sample=sample, stage=Stage.ALIGN).update(file_store_id="store-1")
        monkeypatch.setattr(
            "apps.web_ui.views.dynamodb.get_file_stores",
            lambda ids: {"store-1": {"file_store_id": "store-1", "s3_uri": "s3://bucket/results"}},
        )
        from apps.ocs_integration.s3 import FolderContents

        monkeypatch.setattr(
            "apps.web_ui.views.s3.list_folder",
            lambda uri, prefix, token: FolderContents(
                ["counts"], [{"name": "summary.csv", "key": "results/summary.csv", "size": 12}], None
            ),
        )

        response = logged_in.get(
            reverse("web_ui:data-location-contents", args=[sample.pk, Stage.ALIGN.value])
        )

        assert response.status_code == 200
        assert b"counts/" in response.content
        assert b"summary.csv" in response.content
        assert b"Download selected" in response.content
        assert b"location-file-select" in response.content

        nested_response = logged_in.get(
            reverse("web_ui:data-location-contents", args=[sample.pk, Stage.ALIGN.value]),
            {"prefix": "counts/sub"},
        )

        assert b'aria-label="Go to parent folder"' in nested_response.content
        assert b"prefix=counts" in nested_response.content

    def test_downloads_selected_files_as_one_zip(self, logged_in, monkeypatch, make_sample):
        sample = make_sample("A-1", align="COMPLETED")
        StageStatus.objects.filter(sample=sample, stage=Stage.ALIGN).update(file_store_id="store-1")
        monkeypatch.setattr(
            "apps.web_ui.views.dynamodb.get_file_stores",
            lambda ids: {"store-1": {"file_store_id": "store-1", "s3_uri": "s3://bucket/results"}},
        )
        monkeypatch.setattr("apps.web_ui.views.s3.validate_key", lambda uri, key: None)
        monkeypatch.setattr(
            "apps.web_ui.views.s3.relative_key", lambda uri, key: key.removeprefix("results/")
        )
        monkeypatch.setattr(
            "apps.web_ui.views.s3.get_object_body",
            lambda uri, key: io.BytesIO(key.encode()),
        )

        response = logged_in.post(
            reverse("web_ui:data-location-download", args=[sample.pk, Stage.ALIGN.value]),
            {"keys": ["results/summary.csv", "results/summary.csv", "results/counts.csv"]},
        )

        archive = b"".join(response.streaming_content)
        assert response.status_code == 200
        assert response["Content-Disposition"] == 'attachment; filename="A-1-align.zip"'
        with zipfile.ZipFile(io.BytesIO(archive)) as download:
            assert download.namelist() == ["summary.csv", "counts.csv"]
            assert download.read("summary.csv") == b"results/summary.csv"

    def test_downloads_a_folder_as_one_zip(self, logged_in, monkeypatch, make_sample):
        sample = make_sample("A-1", align="COMPLETED")
        StageStatus.objects.filter(sample=sample, stage=Stage.ALIGN).update(file_store_id="store-1")
        monkeypatch.setattr(
            "apps.web_ui.views.dynamodb.get_file_stores",
            lambda ids: {"store-1": {"file_store_id": "store-1", "s3_uri": "s3://bucket/results"}},
        )
        monkeypatch.setattr(
            "apps.web_ui.views.s3.list_files", lambda uri, prefix: iter(["results/counts/a.csv"])
        )
        monkeypatch.setattr(
            "apps.web_ui.views.s3.relative_key", lambda uri, key: key.removeprefix("results/")
        )
        monkeypatch.setattr("apps.web_ui.views.s3.get_object_body", lambda uri, key: io.BytesIO(b"data"))

        response = logged_in.post(
            reverse("web_ui:data-location-download", args=[sample.pk, Stage.ALIGN.value]),
            {"folders": ["counts"]},
        )

        with zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content))) as download:
            assert download.namelist() == ["counts/a.csv"]

    def test_download_requires_a_selected_file(self, logged_in, monkeypatch, make_sample):
        sample = make_sample("A-1", align="COMPLETED")
        StageStatus.objects.filter(sample=sample, stage=Stage.ALIGN).update(file_store_id="store-1")
        monkeypatch.setattr(
            "apps.web_ui.views.dynamodb.get_file_stores",
            lambda ids: {"store-1": {"file_store_id": "store-1", "s3_uri": "s3://bucket/results"}},
        )

        response = logged_in.post(
            reverse("web_ui:data-location-download", args=[sample.pk, Stage.ALIGN.value])
        )

        assert response.status_code == 400
        assert response.json() == {"error": "Select at least one file or folder."}

    def test_data_locations_export_includes_s3_rows_for_selected_samples(
        self, logged_in, monkeypatch, make_sample
    ):
        sample = make_sample("A-1", align="COMPLETED")
        StageStatus.objects.filter(sample=sample, stage=Stage.ALIGN).update(file_store_id="store-1")
        monkeypatch.setattr(
            "apps.web_ui.views.dynamodb.get_file_stores",
            lambda ids: {"store-1": {"file_store_id": "store-1", "s3_uri": "s3://bucket/results"}},
        )

        response = logged_in.post(reverse("web_ui:data-locations-export"), {"fastq_names": ["A-1"]})

        body = b"".join(response.streaming_content)
        assert response.status_code == 200
        assert b"S3 Location" in body
        assert b"s3://bucket/results" in body
        assert b"A-1" in body

    def test_data_locations_export_respects_the_active_tab(self, logged_in, monkeypatch, make_sample):
        make_sample("MTX-1", batch_name_from_vendor="MTX-10")
        make_sample("RTX-1", batch_name_from_vendor="RTX-20")
        monkeypatch.setattr(
            "apps.web_ui.data_location_queries.dynamodb.get_file_stores",
            lambda ids: {},
        )

        response = logged_in.post(f"{reverse('web_ui:data-locations-export')}?batch_prefix=MTX")

        body = b"".join(response.streaming_content)
        assert b"MTX-1" in body
        assert b"RTX-1" not in body

    def test_data_locations_export_matches_selected_columns_and_stage(
        self, logged_in, monkeypatch, make_sample
    ):
        make_sample("A-1", align="COMPLETED")
        monkeypatch.setattr("apps.web_ui.data_location_queries.dynamodb.get_file_stores", lambda ids: {})
        logged_in.post(
            reverse("web_ui:set-columns"),
            {"scope": "locations", "columns": ["load_name", "stage"]},
        )

        response = logged_in.post(f"{reverse('web_ui:data-locations-export')}?location_stage=align")

        body = b"".join(response.streaming_content)
        assert b"Fastq Name,Load Name,Stage,S3 Location" in body
        assert b"Organism Common Name" not in body
        assert b"A-1" in body

    def test_sync_pulls_a_batch(self, logged_in, monkeypatch, make_sample):
        from apps.sample_catalog import ocs_sync as sync_service

        monkeypatch.setattr(sync_service, "sync_batch", lambda batch_name_from_vendor: [make_sample("NEW-1")])

        response = logged_in.post(
            reverse("web_ui:sync"), {"batch_name_from_vendor": "MTX-22068"}, follow=True
        )

        assert b"Synced 1 samples" in response.content


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


class TestQueue:
    def test_lists_pending_entries_and_the_next_one(self, logged_in, queued):
        queued("READY-1")

        response = logged_in.get(reverse("web_ui:queue"))

        assert b"READY-1" in response.content
        assert b"Next eligible submission" in response.content
        assert f"requested by {response.wsgi_request.user}".encode() in response.content
        assert b"Queue status" in response.content

    def test_users_do_not_see_each_others_queues(self, logged_in, queued, client, django_user_model):
        queued("READY-1")
        other = django_user_model.objects.create_user(username="other", email="o@b.org")
        client.force_login(other)

        assert b"READY-1" not in client.get(reverse("web_ui:queue")).content

    def test_cancelling_a_pending_entry(self, logged_in, queued):
        entry = queued("READY-1")

        logged_in.post(reverse("web_ui:cancel", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert entry.status == QueueEntry.Status.CANCELLED

    def test_pausing_hides_the_next_submission_and_persists(self, logged_in, user, queued):
        queued("READY-1")

        logged_in.post(reverse("web_ui:toggle-queue-pause"), follow=True)

        user.refresh_from_db()
        assert user.queue_paused is True
        response = logged_in.get(reverse("web_ui:queue"))
        assert response.context["queue_paused"] is True
        assert b"Next eligible submission" not in response.content

    def test_resuming_restores_the_next_submission(self, logged_in, user, queued):
        queued("READY-1")
        user.queue_paused = True
        user.save(update_fields=["queue_paused"])

        logged_in.post(reverse("web_ui:toggle-queue-pause"), follow=True)

        user.refresh_from_db()
        assert user.queue_paused is False
        assert b"Next eligible submission" in logged_in.get(reverse("web_ui:queue")).content

    def test_deleting_a_pending_entry_removes_it(self, logged_in, queued):
        entry = queued("READY-1")

        logged_in.post(reverse("web_ui:delete-queue-entry", args=[entry.pk]), follow=True)

        assert not QueueEntry.objects.filter(pk=entry.pk).exists()

    def test_deleting_another_users_entry_is_refused(self, logged_in, queued, client, django_user_model):
        entry = queued("READY-1")
        other = django_user_model.objects.create_user(username="other", email="o@b.org")
        client.force_login(other)

        response = client.post(reverse("web_ui:delete-queue-entry", args=[entry.pk]))

        assert response.status_code == 404
        assert QueueEntry.objects.filter(pk=entry.pk).exists()

    def test_deleting_a_submitting_entry_leaves_it_untouched(self, logged_in, queued):
        entry = queued("READY-1")
        entry.status = QueueEntry.Status.SUBMITTING
        entry.save(update_fields=["status"])

        logged_in.post(reverse("web_ui:delete-queue-entry", args=[entry.pk]), follow=True)

        assert QueueEntry.objects.filter(pk=entry.pk).exists()


class TestJobMonitor:
    """The monitor reads the mirror, so it covers OCS work this app never submitted.

    Driving it from QueueEntry meant an operator watching a busy pipeline saw an empty
    page whenever the demands had been submitted by hand, and meant a job vanished from
    the page the moment somebody deleted its queue entry.
    """

    def test_a_running_stage_appears(self, logged_in, make_sample):
        sample = make_sample("RUNNING-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="demand-123")

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert b"RUNNING-1" in response.content
        assert b"demand-123" in response.content
        assert response.context["counts"]["align"] == 1

    def test_running_stage_filter_shows_only_alignment_jobs(self, logged_in, make_sample):
        alignment = make_sample("RUNNING-ALIGN-1")
        alignment.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS", demand_id="demand-align")
        post_alignment = make_sample("RUNNING-POST-1")
        post_alignment.stage_statuses.create(
            stage=Stage.POST_ALIGN, status="IN_PROGRESS", demand_id="demand-post"
        )

        response = logged_in.get(reverse("web_ui:job-monitor"), {"running_stage": Stage.ALIGN})

        assert [row.sample.fastq_name for row in response.context["running"]] == ["RUNNING-ALIGN-1"]
        assert response.context["counts"] == {"align": 1, "post_align": 0, "total": 1}
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
        assert response.context["counts"] == {"align": 0, "post_align": 1, "total": 1}

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
        for sample in (gex, atac):
            sample.stage_statuses.create(
                stage=Stage.ALIGN, status="IN_PROGRESS", demand_id=f"{sample.pk}-demand"
            )

        response = logged_in.get(reverse("web_ui:job-monitor"))

        assert len(response.context["running"]) == 1
        assert response.context["running"][0].sample == gex
        assert response.context["running"][0].sample.modality == "MTX"
        assert response.context["counts"]["total"] == 1
        assert set(response.context["monitor_fastq_names"]) == {gex.fastq_name, atac.fastq_name}

    def test_a_shared_load_collapses_regardless_of_library_prep_name(self, logged_in, make_sample):
        """The pairing that matters is one load_name aligning as one OCS job; the prep
        name is just whatever the vendor happened to call it, not the tie that binds
        the two rows together."""
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

        with django_assert_num_queries(8):
            logged_in.get(reverse("web_ui:job-monitor"))


class TestFailedJobs:
    def test_lists_failures_with_the_error(self, logged_in, queued):
        entry = queued("BAD-1")
        entry.status = QueueEntry.Status.FAILED
        entry.error_message = "OCS rejected the demand"
        entry.save()

        response = logged_in.get(reverse("web_ui:failed"))

        assert b"OCS rejected the demand" in response.content

    def test_separates_running_ocs_failures_from_submission_failures(self, logged_in, queued):
        entry = queued("OCS-FAILED-1")
        entry.status = QueueEntry.Status.FAILED
        entry.demand_id = "demand-1"
        entry.error_message = "Workflow failed in OCS."
        entry.save()

        response = logged_in.get(reverse("web_ui:failed"))

        assert response.context["entries"] == []
        assert response.context["running_failures"] == [entry]
        assert b"Running job failures" in response.content
        assert b"Workflow failed in OCS." in response.content

    def test_failure_badge_combines_submission_and_running_failures(self, logged_in, queued):
        submission_failure = queued("SUBMISSION-FAILED-1")
        submission_failure.status = QueueEntry.Status.FAILED
        submission_failure.save()
        running_failure = queued("RUNNING-FAILED-1")
        running_failure.status = QueueEntry.Status.FAILED
        running_failure.demand_id = "demand-1"
        running_failure.save()

        response = logged_in.get(reverse("web_ui:failed"))

        assert response.context["failure_count"] == 2
        assert b'<span class="visually-hidden">2 </span>2</span>' in response.content

    def test_retry_puts_it_back_on_the_queue(self, logged_in, queued):
        entry = queued("BAD-1")
        entry.status = QueueEntry.Status.FAILED
        entry.demand_id = "old-demand"
        entry.submitted_at = timezone.now()
        entry.error_message = "boom"
        entry.save()

        logged_in.post(reverse("web_ui:retry", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert entry.status == QueueEntry.Status.PENDING
        assert entry.demand_id == ""
        assert entry.submitted_at is None
        assert entry.error_message == ""

    def test_delete_removes_the_entry(self, logged_in, queued):
        entry = queued("BAD-1")
        entry.status = QueueEntry.Status.FAILED
        entry.save()

        logged_in.post(reverse("web_ui:delete-job", args=[entry.pk]), follow=True)

        assert not QueueEntry.objects.filter(pk=entry.pk).exists()

    def test_a_submitted_entry_cannot_be_deleted(self, logged_in, queued):
        entry = queued("RUNNING-1")
        entry.status = QueueEntry.Status.SUBMITTED
        entry.save()

        logged_in.post(reverse("web_ui:delete-job", args=[entry.pk]), follow=True)

        assert QueueEntry.objects.filter(pk=entry.pk).exists()
