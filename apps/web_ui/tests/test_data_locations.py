"""Data Locations view, contents, download, and export tests."""

from __future__ import annotations

import io
import zipfile

import pytest
from django.urls import reverse

from apps.sample_catalog.models import Stage, StageStatus

pytestmark = pytest.mark.django_db


class TestDataLocations:
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
        assert response.content.count(b">s3://bucket/results</span>") == 1
        assert b"store-1" not in response.content
        assert b"demand-align" not in response.content
        assert (
            b'class="btn btn-sm btn-outline-secondary location-contents-toggle table-icon-tooltip"'
            in response.content
        )
        assert b'data-tooltip="View contents"' in response.content

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
            "apps.web_ui.views.data_locations.dynamodb.get_file_stores",
            lambda ids: {"store-1": {"file_store_id": "store-1", "s3_uri": "s3://bucket/results"}},
        )
        from apps.ocs_integration.s3 import FolderContents

        monkeypatch.setattr(
            "apps.web_ui.views.data_locations.s3.list_folder",
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
            "apps.web_ui.views.data_locations.dynamodb.get_file_stores",
            lambda ids: {"store-1": {"file_store_id": "store-1", "s3_uri": "s3://bucket/results"}},
        )
        monkeypatch.setattr("apps.web_ui.views.data_locations.s3.validate_key", lambda uri, key: None)
        monkeypatch.setattr(
            "apps.web_ui.views.data_locations.s3.relative_key", lambda uri, key: key.removeprefix("results/")
        )
        monkeypatch.setattr(
            "apps.web_ui.views.data_locations.s3.get_object_body",
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
            "apps.web_ui.views.data_locations.dynamodb.get_file_stores",
            lambda ids: {"store-1": {"file_store_id": "store-1", "s3_uri": "s3://bucket/results"}},
        )
        monkeypatch.setattr(
            "apps.web_ui.views.data_locations.s3.list_files",
            lambda uri, prefix: iter(["results/counts/a.csv"]),
        )
        monkeypatch.setattr(
            "apps.web_ui.views.data_locations.s3.relative_key", lambda uri, key: key.removeprefix("results/")
        )
        monkeypatch.setattr(
            "apps.web_ui.views.data_locations.s3.get_object_body",
            lambda uri, key: io.BytesIO(b"data"),
        )

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
            "apps.web_ui.views.data_locations.dynamodb.get_file_stores",
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
            "apps.web_ui.views.data_locations.dynamodb.get_file_stores",
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
