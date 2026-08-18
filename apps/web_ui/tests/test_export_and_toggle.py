"""The dashboard's family toggle, Study Set filter, and CSV export."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.sample_catalog.models import (
    MULTIOME_ATAC_PREP,
    MULTIOME_GEX_PREP,
    Sample,
    Stage,
    StageStatus,
)
from apps.web_ui import columns

pytestmark = pytest.mark.django_db


def make(fastq_name, batch, prep="10xV4", studies=None, load=""):
    return Sample.objects.create(
        fastq_name=fastq_name,
        batch_name_from_vendor=batch,
        organism_common_name="mouse",
        library_prep_method_name=prep,
        studies=studies or [],
        load_name=load,
    )


class TestFamilyToggle:
    def test_filters_by_vendor_family(self, logged_in):
        make("MTX-1", "MTX-32013")
        make("PLAIN-1", "10X120")

        response = logged_in.get(reverse("web_ui:dashboard"), {"batch_prefix": "MTX"})

        assert b"MTX-1" in response.content
        assert b"PLAIN-1" not in response.content

    def test_atx_is_selectable_separately_from_mtx(self, logged_in):
        """The reason batch_prefix and modality are two columns: ATX runs as MTX but is
        still its own family, so the toggle must be able to isolate it."""
        make("GEX-1", "MTX-32013")
        make("ATAC-1", "ATX-36013")

        response = logged_in.get(reverse("web_ui:dashboard"), {"batch_prefix": "ATX"})

        assert b"ATAC-1" in response.content
        assert b"GEX-1" not in response.content
        assert Sample.objects.get(fastq_name="ATAC-1").modality == "MTX"

    def test_counts_every_family_including_empty_ones(self, logged_in):
        make("MTX-1", "MTX-32013")

        response = logged_in.get(reverse("web_ui:dashboard"))

        counts = {row["value"]: row["count"] for row in response.context["batch_prefixes"]}
        assert counts == {"MTX": 1, "RFX": 0, "ATX": 0, "RTX": 0}

    def test_the_tabs_read_in_the_order_the_lab_thinks_in(self, logged_in):
        """Not the order `BatchPrefix` declares, which answers to the data rather than to
        anyone reading the page."""
        response = logged_in.get(reverse("web_ui:dashboard"))

        assert [row["value"] for row in response.context["batch_prefixes"]] == [
            "RTX",
            "RFX",
            "MTX",
            "ATX",
        ]

    def test_an_unknown_family_is_ignored_rather_than_erroring(self, logged_in):
        make("MTX-1", "MTX-32013")

        response = logged_in.get(reverse("web_ui:dashboard"), {"batch_prefix": "NOPE"})

        assert response.status_code == 200
        assert b"MTX-1" in response.content


class TestStudySet:
    def test_filters_by_study(self, logged_in):
        make("A-1", "10X120", studies=["SCORCH"])
        make("B-1", "10X121", studies=["Aging_Mouse"])

        response = logged_in.get(reverse("web_ui:dashboard"), {"study": "SCORCH"})

        assert b"A-1" in response.content
        assert b"B-1" not in response.content

    def test_filters_by_multiple_studies(self, logged_in):
        make("A-1", "10X120", studies=["SCORCH"])
        make("B-1", "10X121", studies=["Aging_Mouse"])
        make("C-1", "10X122", studies=["Other"])

        response = logged_in.get(
            reverse("web_ui:dashboard"),
            [("study", "SCORCH"), ("study", "Aging_Mouse")],
        )

        assert b"A-1" in response.content
        assert b"B-1" in response.content
        assert b"C-1" not in response.content

    def test_offers_each_study_once(self, logged_in):
        make("A-1", "10X120", studies=["SCORCH", "Aging_Mouse"])
        make("B-1", "10X121", studies=["SCORCH"])

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.context["studies"] == ["Aging_Mouse", "SCORCH"]


class TestExport:
    def _body(self, response) -> str:
        return b"".join(response.streaming_content).decode()

    def test_exports_the_filtered_rows_when_nothing_is_ticked(self, logged_in):
        make("MTX-1", "MTX-32013")
        make("PLAIN-1", "10X120")

        response = logged_in.post(f"{reverse('web_ui:export')}?batch_prefix=MTX")

        body = self._body(response)
        assert "MTX-1" in body
        assert "PLAIN-1" not in body

    def test_a_ticked_selection_wins_over_the_filters(self, logged_in):
        make("A-1", "10X120")
        make("B-1", "10X121")

        response = logged_in.post(reverse("web_ui:export"), {"fastq_names": ["A-1"]})

        body = self._body(response)
        assert "A-1" in body
        assert "B-1" not in body

    def test_is_a_csv_download(self, logged_in):
        make("A-1", "10X120")

        response = logged_in.post(reverse("web_ui:export"))

        assert response["Content-Type"] == "text/csv"
        assert "attachment" in response["Content-Disposition"]

    def test_headers_match_the_users_chosen_columns(self, logged_in):
        make("A-1", "10X120")
        logged_in.post(reverse("web_ui:set-columns"), {"columns": ["fastq_name", "modality"]})

        body = self._body(logged_in.post(reverse("web_ui:export")))

        assert body.splitlines()[0] == "Fastq Name,Workflow"
        assert body.splitlines()[1] == "A-1,RTX"

    def test_a_formula_like_value_is_defused(self, logged_in):
        """Excel executes a cell beginning with an equals sign, plus sign, minus sign, or at sign."""
        make("=cmd|calc", "10X120")
        logged_in.post(reverse("web_ui:set-columns"), {"columns": ["fastq_name"]})

        body = self._body(logged_in.post(reverse("web_ui:export")))

        assert "'=cmd|calc" in body

    def test_requires_login(self, client):
        response = client.post(reverse("web_ui:export"))

        assert response.status_code == 302
        assert "/accounts/login/" in response["Location"]


class TestPairingInSubmission:
    def test_submitting_one_half_pulls_in_the_other(self, logged_in, active_config):
        make("NW-MX32013-2", "MTX-32013", prep=MULTIOME_GEX_PREP, load="3492_A01")
        make("NW-AT36013-2", "ATX-36013", prep=MULTIOME_ATAC_PREP, load="3492_A01")

        response = logged_in.post(
            reverse("web_ui:submit-review"), {"fastq_names": ["NW-MX32013-2"]}, follow=True
        )

        assert b"NW-AT36013-2" in response.content
        assert b"multiome partner" in response.content


class TestScopedFilters:
    def test_filter_menus_only_offer_values_from_the_current_tab(self, logged_in):
        make("MTX-1", "MTX-32013", prep="10xMultX_GEX")
        make("RTX-1", "RTX-8001", prep="10xV3.1")

        response = logged_in.get(reverse("web_ui:dashboard"), {"batch_prefix": "MTX"})

        assert response.context["batches"] == ["MTX-32013"]
        assert response.context["library_preps"] == ["10xMultX_GEX"]

    def test_without_a_tab_every_value_is_offered(self, logged_in):
        make("MTX-1", "MTX-32013")
        make("RTX-1", "RTX-8001")

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.context["batches"] == ["MTX-32013", "RTX-8001"]

    def test_a_selected_batch_survives_an_empty_sync(self, logged_in):
        """The sync redirect keeps its batch in the query even when nothing came back."""
        make("MTX-1", "MTX-32013")

        response = logged_in.get(
            reverse("web_ui:dashboard"), {"batch_prefix": "MTX", "batch_name_from_vendor": "MTX-99999"}
        )

        assert "MTX-99999" in response.context["batches"]


class TestSorting:
    def test_defaults_to_the_highest_batch_number_first(self, logged_in):
        for batch in ("MTX-22053", "MTX-22055", "MTX-22054"):
            make(f"s-{batch}", batch)

        response = logged_in.get(reverse("web_ui:dashboard"))

        shown = [s.batch_name_from_vendor for s in response.context["page"]]
        assert shown == ["MTX-22055", "MTX-22054", "MTX-22053"]

    def test_batches_sort_numerically_not_as_text(self, logged_in):
        """As text "MTX-9" sorts above "MTX-10", which is the wrong "highest first"."""
        for batch in ("MTX-9", "MTX-10", "MTX-100"):
            make(f"s-{batch}", batch)

        response = logged_in.get(reverse("web_ui:dashboard"))

        shown = [s.batch_name_from_vendor for s in response.context["page"]]
        assert shown == ["MTX-100", "MTX-10", "MTX-9"]

    def test_a_column_can_be_sorted_ascending(self, logged_in):
        make("b-1", "MTX-2")
        make("a-1", "MTX-1")

        response = logged_in.get(reverse("web_ui:dashboard"), {"sort": "fastq_name", "dir": "asc"})

        assert [s.fastq_name for s in response.context["page"]] == ["a-1", "b-1"]

    def test_an_unknown_sort_key_falls_back_rather_than_erroring(self, logged_in):
        """order_by takes a field path, so the parameter is an allowlist, not a passthrough."""
        make("a-1", "MTX-1")

        response = logged_in.get(reverse("web_ui:dashboard"), {"sort": "password", "dir": "asc"})

        assert response.status_code == 200
        assert response.context["sort"] == "batch_name_from_vendor"

    def test_sorting_keeps_the_active_tab(self, logged_in):
        make("MTX-1", "MTX-32013")
        make("RTX-1", "RTX-8001")

        response = logged_in.get(
            reverse("web_ui:dashboard"), {"batch_prefix": "MTX", "sort": "fastq_name", "dir": "asc"}
        )

        assert [s.fastq_name for s in response.context["page"]] == ["MTX-1"]


class TestFreshnessTooltip:
    def test_says_how_often_each_sweep_runs(self, logged_in):
        make("a-1", "MTX-1")

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.context["status_refresh"] == "every 5 minutes"
        assert b"refreshes every 5 minutes" in response.content
        assert b"refreshes nightly at 03:00" in response.content


class TestBatchDropdownOrder:
    def test_batches_are_offered_newest_first(self, logged_in):
        for batch in ("MTX-22053", "MTX-22055", "MTX-22054"):
            make(f"s-{batch}", batch)

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.context["batches"] == ["MTX-22055", "MTX-22054", "MTX-22053"]

    def test_the_menu_sorts_numerically_like_the_table(self, logged_in):
        """Alphabetically MTX-12001 would come before MTX-2001, and MTX-9 after MTX-10."""
        for batch in ("MTX-2001", "MTX-12001", "MTX-9", "MTX-10"):
            make(f"s-{batch}", batch)

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.context["batches"] == ["MTX-12001", "MTX-2001", "MTX-10", "MTX-9"]

    def test_a_batch_with_no_digits_sorts_last_rather_than_crashing(self, logged_in):
        make("s-1", "MTX-2001")
        make("s-2", "LEGACY")

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.context["batches"] == ["MTX-2001", "LEGACY"]

    def test_a_kept_selection_is_placed_in_order(self, logged_in):
        make("s-1", "MTX-22053")

        response = logged_in.get(reverse("web_ui:dashboard"), {"batch_name_from_vendor": "MTX-22099"})

        assert response.context["batches"] == ["MTX-22099", "MTX-22053"]


class TestPagerKeepsFilters:
    """Paging used to link to a bare `?page=N`, which dropped every active filter."""

    def test_the_next_page_link_carries_the_current_filters(self, logged_in):
        for index in range(60):
            make(f"mtx-{index:03d}", "MTX-1")
        make("rtx-1", "RTX-9")

        response = logged_in.get(reverse("web_ui:dashboard"), {"batch_prefix": "MTX", "sort": "load_name"})
        html = response.content.decode()

        assert "batch_prefix=MTX" in html and "sort=load_name" in html
        # and the pager's own link is one of the places carrying them
        assert re.search(r'href="\?[^"]*page=2[^"]*"', html)
        assert 'href="?page=2"' not in html, "the pager dropped the active filters"


class TestFreshnessIsStateful:
    def test_a_sweep_that_has_missed_several_turns_reads_as_stale(self, logged_in):
        sample = make("a-1", "MTX-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS")
        StageStatus.objects.update(synced_at=timezone.now() - timedelta(hours=4))

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.context["status_stale"] is True
        assert b'data-state="warn"' in response.content
        assert b"The sync worker may not be running" in response.content

    def test_a_fresh_sweep_does_not(self, logged_in):
        sample = make("a-1", "MTX-1")
        sample.stage_statuses.create(stage=Stage.ALIGN, status="IN_PROGRESS")
        StageStatus.objects.update(synced_at=timezone.now())

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.context["status_stale"] is False


class TestExportStageColumns:
    """BKP Codex export is the fourth stage: shown, never submitted."""

    def test_status_and_demand_id_are_offered(self):
        keys = {column.key for column in columns.COLUMNS}
        assert "status:export" in keys
        assert "demand:export" in keys
        assert "status:export" in columns.DEFAULT_COLUMNS

    def test_no_file_store_id_column_for_export(self):
        """An export demand records inputs and no outputs, so the value cannot arrive.

        Offering the column anyway would put a permanently empty checkbox in the chooser.
        """
        keys = {column.key for column in columns.COLUMNS}
        assert "filestore:export" not in keys
        assert {"filestore:ingest", "filestore:align", "filestore:post-align"} <= keys
