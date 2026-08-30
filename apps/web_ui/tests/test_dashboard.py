"""Dashboard, filtering, paging, and CSV export tests."""

from __future__ import annotations

import re

import pytest
from django.test import Client
from django.urls import reverse

from apps.ocs_integration import dynamodb
from apps.sample_catalog import ocs_sync as sync
from apps.sample_catalog.models import NOT_COMPLETED, Sample, Stage
from apps.submission_queue.models import CartItem
from apps.web_ui import columns
from apps.web_ui import columns as column_defs
from apps.web_ui import views as web_views

pytestmark = pytest.mark.django_db


def messages_in(response) -> str:
    return response.content.decode()


def csv_body(response) -> str:
    return b"".join(response.streaming_content).decode()


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
        """The identifying column remains visible when the user hides other columns."""
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

    def test_searches_fastq_load_and_batch_name_from_vendor_values(self, logged_in, make_sample):
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
        """The local data is still readable; only the live read failed, and the table stays up."""
        from botocore.exceptions import EndpointConnectionError

        from apps.sample_catalog import ocs_sync as sync_service

        make_sample("A-1")

        def _boom(samples):
            raise EndpointConnectionError(endpoint_url="https://dynamodb.us-west-2.amazonaws.com")

        monkeypatch.setattr(sync_service, "sync_stage_statuses", _boom)

        response = logged_in.post(reverse("web_ui:refresh-status"), {"fastq_names": ["A-1"]}, follow=True)

        assert response.status_code == 200
        assert b"Could not reach OCS" in response.content


class TestSignedOut:
    # job-monitor is deliberately absent: it is being rewritten alongside these tests.
    PAGES = [
        "web_ui:dashboard",
        "web_ui:queue",
        "web_ui:failed",
        "web_ui:checkout",
        "web_ui:configs",
    ]

    @pytest.mark.parametrize("name", PAGES)
    def test_a_page_sends_you_to_sign_in_and_remembers_where_you_were(self, client, name):
        target = reverse(name)

        response = client.get(target)

        assert response.status_code == 302
        assert response["Location"] == f"{reverse('login')}?next={target}"

    def test_signing_in_lands_you_back_on_the_page_you_asked_for(self, client, user):
        target = reverse("web_ui:queue")

        response = client.post(
            f"{reverse('login')}?next={target}",
            {"username": user.get_username(), "password": "password"},
        )

        assert response.status_code == 302
        assert response["Location"] == target

    def test_a_post_only_endpoint_also_preserves_where_you_were(self, client):
        response = client.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        assert response.status_code == 302
        assert response["Location"] == f"{reverse('login')}?next={reverse('web_ui:cart-add')}"

    def test_the_health_endpoint_answers_without_signing_in(self, client):
        response = client.get(reverse("health"))

        # 503 is a legitimate answer here (no worker heartbeat in a test run); what must
        # never happen is a redirect to the sign-in form, which a monitor reads as healthy.
        assert response.status_code in (200, 503)
        assert response["Content-Type"].startswith("application/json")
        assert "database" in response.json()["checks"]

    def test_signing_up_gets_you_in_but_not_into_the_admin(self, client, django_user_model):
        response = client.post(
            reverse("accounts:signup"),
            {"username": "newcomer", "password1": "correct-horse-42", "password2": "correct-horse-42"},
            follow=True,
        )

        account = django_user_model.objects.get(username="newcomer")
        assert response.status_code == 200
        assert not account.is_staff and not account.is_superuser
        assert client.get(reverse("admin:index")).status_code in (302, 403)

    def test_logging_out_says_so(self, logged_in):
        response = logged_in.post(reverse("logout"), follow=True)

        assert b"You&#x27;ve been signed out." in response.content
        assert response.wsgi_request.user.is_authenticated is False


class TestDashboardFilters:
    @pytest.fixture(autouse=True)
    def local_database(self, make_sample):
        make_sample("MOUSE-MTX", batch_name_from_vendor="MTX-100", organism_common_name="mouse")
        make_sample(
            "HUMAN-RTX",
            batch_name_from_vendor="RTX-200",
            organism_common_name="human",
            library_prep_method_name="10xV4",
            align="COMPLETED",
        )
        make_sample(
            "RAT-RFX",
            batch_name_from_vendor="RFX-300",
            organism_common_name="rat",
            library_prep_method_name="10xFXv2",
            ingest=NOT_COMPLETED,
        )

    def rows(self, response) -> set[str]:
        return {sample.fastq_name for sample in response.context["page"].object_list}

    def test_one_filter_narrows_the_table(self, logged_in):
        response = logged_in.get(reverse("web_ui:dashboard"), {"organism_common_name": "human"})

        assert self.rows(response) == {"HUMAN-RTX"}

    def test_search_matches_fastq_or_load_name(self, logged_in, make_sample):
        make_sample("LOAD-MATCH", load_name="LOAD-123")

        response = logged_in.get(reverse("web_ui:dashboard"), {"fastq_name": "LOAD-123"})

        assert self.rows(response) == {"LOAD-MATCH"}

    def test_filters_combine_rather_than_replace_each_other(self, logged_in):
        response = logged_in.get(
            reverse("web_ui:dashboard"),
            {
                "batch_prefix": "RTX",
                "organism_common_name": "human",
                "library_prep_method_name": "10xV4",
                "align_status": "COMPLETED",
                "ingest_status": "INGEST_COMPLETE",
                "study": "StudyA",
                "fastq_name": "HUMAN",
            },
        )

        assert self.rows(response) == {"HUMAN-RTX"}

    def test_a_combination_that_matches_nothing_is_an_empty_table_not_an_error(self, logged_in):
        response = logged_in.get(
            reverse("web_ui:dashboard"), {"organism_common_name": "human", "batch_prefix": "MTX"}
        )

        assert response.status_code == 200
        assert self.rows(response) == set()

    def test_the_not_completed_status_finds_stages_ocs_never_ran(self, logged_in):
        response = logged_in.get(reverse("web_ui:dashboard"), {"ingest_status": NOT_COMPLETED})

        assert self.rows(response) == {"RAT-RFX"}

    def test_an_unknown_family_tab_shows_everything_rather_than_nothing(self, logged_in):
        response = logged_in.get(reverse("web_ui:dashboard"), {"batch_prefix": "ZZZ"})

        assert response.status_code == 200
        assert self.rows(response) == {"MOUSE-MTX", "HUMAN-RTX", "RAT-RFX"}

    def test_the_active_filter_count_matches_what_is_narrowing_the_table(self, logged_in):
        response = logged_in.get(
            reverse("web_ui:dashboard"),
            {"organism_common_name": "human", "library_prep_method_name": "10xV4"},
        )

        assert response.context["active_filter_count"] == 2
        assert response.context["filters_open"] is True

    def test_a_study_the_local_database_has_never_heard_of_returns_nothing(self, logged_in):
        response = logged_in.get(reverse("web_ui:dashboard"), {"study": "NoSuchStudy"})

        assert response.status_code == 200
        assert self.rows(response) == set()

    def test_switching_family_tab_keeps_every_other_filter(self, logged_in):
        response = logged_in.get(
            reverse("web_ui:dashboard"),
            {"organism_common_name": "human", "fastq_name": "HUMAN", "align_status": "COMPLETED"},
        )

        # The tab links used to be hand-built hrefs that carried only batch_prefix, so
        # clicking a family quietly widened the view back to the whole local database.
        html = messages_in(response)
        for tab_link in [line for line in html.splitlines() if "batch_prefix=" in line]:
            assert "organism_common_name=human" in tab_link
            assert "fastq_name=HUMAN" in tab_link
            assert "align_status=COMPLETED" in tab_link

    def test_a_study_that_has_just_been_synced_can_be_filtered_on(self, logged_in, monkeypatch, make_sample):
        """The study menu is cached, so a sync has to drop it or the new study is unfindable.

        Patched at the DynamoDB boundary rather than at `sync_batch`, so the real
        `_upsert_samples` runs. It invalidates the cached menu, and a
        stub in front of it would be testing the stub.
        """
        assert logged_in.get(reverse("web_ui:dashboard")).context["studies"] == ["StudyA"]

        monkeypatch.setattr(
            dynamodb,
            "get_metadata_by_batch",
            lambda batch: [
                {
                    "fastq_name": "FRESH-1",
                    "batch_name_from_vendor": batch,
                    "organism_common_name": "mouse",
                    "library_prep_method_name": "10xRSeq_Mult",
                    "studies": ["StudyB"],
                }
            ],
        )
        monkeypatch.setattr(sync, "sync_stage_statuses", lambda samples: None)

        logged_in.post(reverse("web_ui:sync"), {"batch_name_from_vendor": "MTX-999"}, follow=True)

        response = logged_in.get(reverse("web_ui:dashboard"))
        assert response.context["studies"] == ["StudyA", "StudyB"]
        assert self.rows(logged_in.get(reverse("web_ui:dashboard"), {"study": "StudyB"})) == {"FRESH-1"}

    def test_the_search_box_keeps_what_was_typed(self, logged_in):
        response = logged_in.get(reverse("web_ui:dashboard"), {"fastq_name": "HUMAN"})

        assert response.context["search"] == "HUMAN"
        assert self.rows(response) == {"HUMAN-RTX"}


class TestPagingAndSorting:
    @pytest.fixture
    def many(self, make_sample):
        for index in range(55):
            make_sample(f"BULK-{index:03d}", batch_name_from_vendor=f"MTX-{index:05d}")

    def test_page_beyond_the_end_shows_the_last_page(self, logged_in, many):
        response = logged_in.get(reverse("web_ui:dashboard"), {"page": "999"})

        page = response.context["page"]
        assert response.status_code == 200
        assert page.number == page.paginator.num_pages == 2

    def test_a_page_number_that_is_not_a_number_shows_the_first_page(self, logged_in, many):
        response = logged_in.get(reverse("web_ui:dashboard"), {"page": "abc"})

        assert response.status_code == 200
        assert response.context["page"].number == 1

    def test_an_unknown_sort_key_falls_back_to_the_default(self, logged_in, many):
        response = logged_in.get(reverse("web_ui:dashboard"), {"sort": "'; DROP TABLE"})

        assert response.status_code == 200
        assert response.context["sort"] == web_views.DEFAULT_SORT

    @pytest.mark.parametrize("key", sorted(web_views.SORTABLE))
    @pytest.mark.parametrize("direction", ["asc", "desc"])
    def test_every_sortable_column_sorts_both_ways(self, logged_in, make_sample, key, direction):
        make_sample("SORT-A", batch_name_from_vendor="MTX-1")
        make_sample("SORT-B", batch_name_from_vendor="MTX-2")

        response = logged_in.get(reverse("web_ui:dashboard"), {"sort": key, "dir": direction})

        assert response.status_code == 200
        assert response.context["sort"] == key
        assert response.context["dir"] == direction
        assert len(response.context["page"].object_list) == 2

    def test_sorting_by_batch_reads_the_number_not_the_text(self, logged_in, make_sample):
        make_sample("LOW", batch_name_from_vendor="MTX-9")
        make_sample("HIGH", batch_name_from_vendor="MTX-10")

        response = logged_in.get(
            reverse("web_ui:dashboard"), {"sort": "batch_name_from_vendor", "dir": "desc"}
        )

        assert [s.fastq_name for s in response.context["page"].object_list] == ["HIGH", "LOW"]

    def test_paging_keeps_the_filters(self, logged_in, make_sample):
        for index in range(55):
            make_sample(f"KEEP-{index:03d}", organism_common_name="human")
        make_sample("OTHER", organism_common_name="mouse")

        response = logged_in.get(reverse("web_ui:dashboard"), {"organism_common_name": "human", "page": "2"})

        assert response.context["page"].number == 2
        assert all(s.organism_common_name == "human" for s in response.context["page"].object_list)
        assert response.context["page"].paginator.count == 55

    def test_the_pager_link_carries_the_filters_and_the_sort(self, logged_in, make_sample):
        for index in range(55):
            make_sample(f"KEEP-{index:03d}", organism_common_name="human")

        response = logged_in.get(
            reverse("web_ui:dashboard"),
            {"organism_common_name": "human", "sort": "load_name", "dir": "asc"},
        )

        pager = [
            line for line in messages_in(response).splitlines() if "pager__step" in line and "href=" in line
        ]
        assert pager, "expected a next-page link"
        for link in pager:
            assert "organism_common_name=human" in link
            assert "sort=load_name" in link and "dir=asc" in link

    def test_re_sorting_drops_the_page_so_you_land_at_the_top(self, logged_in, make_sample):
        for index in range(55):
            make_sample(f"KEEP-{index:03d}")

        response = logged_in.get(reverse("web_ui:dashboard"), {"page": "2"})

        header_links = [line for line in messages_in(response).splitlines() if "sort=load_name" in line]
        assert header_links
        assert all("page=" not in link for link in header_links)


class TestColumnChoices:
    def test_a_chosen_set_of_columns_persists_for_that_user(self, logged_in, make_sample, user, client):
        make_sample("READY-1", load_name="LOAD_XYZ")

        logged_in.post(reverse("web_ui:set-columns"), {"columns": ["fastq_name", "load_name"]})

        user.refresh_from_db()
        assert user.visible_columns == ["fastq_name", "load_name"]
        client.force_login(user)
        labels = [column.label for column in client.get(reverse("web_ui:dashboard")).context["columns"]]
        assert labels == ["Fastq Name", "Load Name"]

    def test_one_users_columns_do_not_follow_another_user(self, logged_in, other_client, make_sample):
        make_sample("READY-1")
        logged_in.post(reverse("web_ui:set-columns"), {"columns": ["fastq_name", "load_name"]})

        their_columns = other_client.get(reverse("web_ui:dashboard")).context["columns"]

        assert {c.key for c in their_columns} == set(column_defs.DEFAULT_COLUMNS)

    def test_the_fastq_name_column_cannot_be_dropped(self, logged_in, make_sample, user):
        make_sample("READY-1")

        logged_in.post(reverse("web_ui:set-columns"), {"columns": ["load_name", "modality"]})

        user.refresh_from_db()
        assert user.visible_columns[0] == "fastq_name"
        assert b"READY-1" in logged_in.get(reverse("web_ui:dashboard")).content

    def test_clearing_every_box_still_leaves_a_readable_table(self, logged_in, make_sample, user):
        make_sample("READY-1")

        logged_in.post(reverse("web_ui:set-columns"), {"columns": []})

        user.refresh_from_db()
        assert user.visible_columns == ["fastq_name"]
        assert b"READY-1" in logged_in.get(reverse("web_ui:dashboard")).content

    def test_a_column_key_that_does_not_exist_is_ignored(self, logged_in, make_sample, user):
        make_sample("READY-1")

        response = logged_in.post(
            reverse("web_ui:set-columns"),
            {"columns": ["load_name", "password", "sample__user__password"]},
            follow=True,
        )

        user.refresh_from_db()
        assert response.status_code == 200
        assert user.visible_columns == ["fastq_name", "load_name"]

    def test_a_stale_column_key_left_on_the_account_does_not_break_the_table(
        self, logged_in, make_sample, user
    ):
        make_sample("READY-1")
        user.visible_columns = ["fastq_name", "a_column_that_was_removed"]
        user.save(update_fields=["visible_columns"])

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.status_code == 200
        assert [c.key for c in response.context["columns"]] == ["fastq_name"]


class TestCsvExport:
    def test_it_exports_what_the_filters_are_showing(self, logged_in, make_sample):
        make_sample("MOUSE-1", organism_common_name="mouse")
        make_sample("HUMAN-1", organism_common_name="human")

        response = logged_in.post(f"{reverse('web_ui:export')}?organism_common_name=human")

        body = csv_body(response)
        assert "HUMAN-1" in body and "MOUSE-1" not in body
        assert re.fullmatch(
            r'attachment; filename="\d{2}-\d{2}-\d{4}_\d{4}_export\.csv"',
            response["Content-Disposition"],
        )

    def test_a_ticked_selection_narrows_the_export_further(self, logged_in, make_sample):
        make_sample("HUMAN-1", organism_common_name="human")
        make_sample("HUMAN-2", organism_common_name="human")

        response = logged_in.post(
            f"{reverse('web_ui:export')}?organism_common_name=human", {"fastq_names": ["HUMAN-1"]}
        )

        body = csv_body(response)
        assert "HUMAN-1" in body and "HUMAN-2" not in body

    def test_the_header_row_is_the_users_chosen_columns(self, logged_in, make_sample):
        make_sample("READY-1", load_name="LOAD_XYZ")
        logged_in.post(reverse("web_ui:set-columns"), {"columns": ["fastq_name", "load_name"]})

        header, first = csv_body(logged_in.post(reverse("web_ui:export"))).splitlines()[:2]

        assert header == "Fastq Name,Load Name"
        assert first == "READY-1,LOAD_XYZ"

    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
    def test_a_value_a_spreadsheet_would_run_as_a_formula_is_defused(self, logged_in, make_sample, prefix):
        make_sample("READY-1", batch_name_from_vendor=f'{prefix}HYPERLINK("http://evil")')

        body = csv_body(logged_in.post(reverse("web_ui:export")))

        assert f"'{prefix}HYPERLINK" in body

    def test_an_export_of_nothing_is_still_a_valid_file_with_headers(self, logged_in):
        body = csv_body(logged_in.post(f"{reverse('web_ui:export')}?organism_common_name=nobody"))

        assert body.splitlines()[0].startswith("Fastq Name")
        assert len(body.splitlines()) == 1


class TestOddData:
    def test_a_sample_ocs_has_no_status_for_at_all_still_renders(self, logged_in, make_sample):
        make_sample("BLANK-1", ingest=NOT_COMPLETED)

        response = logged_in.get(reverse("web_ui:dashboard"))

        assert response.status_code == 200
        assert b"BLANK-1" in response.content
        assert b"NOT COMPLETED" in response.content

    def test_a_batch_name_with_no_digits_does_not_break_the_table(self, logged_in, make_sample):
        make_sample("NODIGITS-1", batch_name_from_vendor="MTX-PILOT")
        make_sample("NUMBERED-1", batch_name_from_vendor="MTX-42")

        response = logged_in.get(
            reverse("web_ui:dashboard"), {"sort": "batch_name_from_vendor", "dir": "desc"}
        )

        assert response.status_code == 200
        assert {s.fastq_name for s in response.context["page"].object_list} == {
            "NODIGITS-1",
            "NUMBERED-1",
        }

    def test_the_batch_menu_and_the_table_agree_on_where_a_digitless_batch_goes(self, logged_in, make_sample):
        make_sample("NODIGITS-1", batch_name_from_vendor="MTX-PILOT")
        make_sample("NUMBERED-1", batch_name_from_vendor="MTX-42")

        response = logged_in.get(
            reverse("web_ui:dashboard"), {"sort": "batch_name_from_vendor", "dir": "desc"}
        )

        menu_order = response.context["batches"]
        table_order = [s.batch_name_from_vendor for s in response.context["page"].object_list]
        assert menu_order == ["MTX-42", "MTX-PILOT"]
        assert table_order == menu_order

    @pytest.mark.parametrize(
        "term", ["マウス", "café", "%", "NOT_FOUND_", "100%_", "'; DROP TABLE catalog_sample; --"]
    )
    def test_an_awkward_search_term_returns_nothing_rather_than_erroring(self, logged_in, make_sample, term):
        make_sample("READY-1")

        response = logged_in.get(reverse("web_ui:dashboard"), {"fastq_name": term})

        assert response.status_code == 200
        assert list(response.context["page"].object_list) == []
        assert Sample.objects.filter(fastq_name="READY-1").exists()

    def test_a_search_term_longer_than_the_column_is_survivable(self, logged_in, make_sample):
        make_sample("READY-1")

        response = logged_in.get(reverse("web_ui:dashboard"), {"fastq_name": "x" * 5000})

        assert response.status_code == 200
        assert list(response.context["page"].object_list) == []

    def test_a_unicode_batch_name_survives_the_round_trip(self, logged_in, make_sample):
        make_sample("UNI-1", batch_name_from_vendor="MTX-Ω-22068")

        response = logged_in.get(reverse("web_ui:dashboard"), {"batch_name_from_vendor": "MTX-Ω-22068"})

        assert [s.fastq_name for s in response.context["page"].object_list] == ["UNI-1"]
        assert "MTX-Ω-22068" in csv_body(logged_in.post(reverse("web_ui:export")))

    def test_a_post_without_a_csrf_token_is_refused(self, user, make_sample):
        make_sample("READY-1")
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(user)

        response = strict.post(reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"]})

        assert response.status_code == 403
        assert not CartItem.objects.exists()

    def test_a_get_on_a_post_only_endpoint_is_refused(self, logged_in):
        assert logged_in.get(reverse("web_ui:cart-clear")).status_code == 405

    def test_a_redirect_target_pointing_off_site_is_ignored(self, logged_in, make_sample):
        make_sample("READY-1")

        response = logged_in.post(
            reverse("web_ui:cart-add"), {"fastq_names": ["READY-1"], "next": "https://evil.example/steal"}
        )

        assert response["Location"] == reverse("web_ui:dashboard")

    def test_syncing_without_a_batch_name_asks_for_one(self, logged_in):
        response = logged_in.post(reverse("web_ui:sync"), {"batch_name_from_vendor": ""}, follow=True)

        assert b"Enter a batch name to sync" in response.content

    def test_refreshing_status_for_rows_that_are_gone_says_so(self, logged_in):
        response = logged_in.post(reverse("web_ui:refresh-status"), {"fastq_names": ["GHOST-1"]}, follow=True)

        assert b"No samples to refresh" in response.content
