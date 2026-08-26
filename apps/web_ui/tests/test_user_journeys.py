"""Test OmicsHub user journeys through real URLs and responses.

Each test signs in, filters, selects columns, fills a cart, plans and confirms a submission,
or inspects the resulting response.
"""

from __future__ import annotations

import json
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.ocs_integration import dynamodb
from apps.sample_catalog import ocs_sync as sync
from apps.sample_catalog.models import NOT_COMPLETED, Sample, Stage
from apps.submission_queue.models import CartItem, QueueEntry
from apps.web_ui import columns as column_defs
from apps.web_ui import views as web_views
from apps.workflow_engine.models import WorkflowConfig

pytestmark = pytest.mark.django_db


# --- shared helpers ----------------------------------------------------------------------


@pytest.fixture
def other_user(db, django_user_model):
    """Create a second ordinary account. Staff can see every user's queue."""
    return django_user_model.objects.create_user(
        username="colleague", email="colleague@alleninstitute.org", password="password"
    )


@pytest.fixture
def other_client(other_user):
    client = Client()
    client.force_login(other_user)
    return client


@pytest.fixture
def staff_user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="curator", email="curator@alleninstitute.org", password="password", is_staff=True
    )


@pytest.fixture
def staff_client(staff_user):
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def submit(logged_in):
    """Post a whole submission the way the confirm modal does."""

    def _submit(fastq_names, **extra):
        return logged_in.post(
            reverse("web_ui:submit-confirm"), {"fastq_names": list(fastq_names), **extra}, follow=True
        )

    return _submit


@pytest.fixture
def review(logged_in):
    """Post step one of the submit flow and return the rendered review page."""

    def _review(fastq_names, **extra):
        return logged_in.post(reverse("web_ui:submit-review"), {"fastq_names": list(fastq_names), **extra})

    return _review


@pytest.fixture
def queued_entry(logged_in, active_config, make_sample):
    """Queue one job through the real flow and hand back its entry."""

    def _queued(fastq_name="READY-1", *, owner_client=None, **sample_kwargs):
        make_sample(fastq_name, **sample_kwargs)
        (owner_client or logged_in).post(reverse("web_ui:submit-confirm"), {"fastq_names": [fastq_name]})
        return QueueEntry.objects.get(sample__fastq_name=fastq_name)

    return _queued


def messages_in(response) -> str:
    return response.content.decode()


# --- 1. signed out -----------------------------------------------------------------------


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


# --- 2. dashboard filters ----------------------------------------------------------------


class TestDashboardFilters:
    @pytest.fixture(autouse=True)
    def mirror(self, make_sample):
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

    def test_a_study_the_mirror_has_never_heard_of_returns_nothing(self, logged_in):
        response = logged_in.get(reverse("web_ui:dashboard"), {"study": "NoSuchStudy"})

        assert response.status_code == 200
        assert self.rows(response) == set()

    def test_switching_family_tab_keeps_every_other_filter(self, logged_in):
        response = logged_in.get(
            reverse("web_ui:dashboard"),
            {"organism_common_name": "human", "fastq_name": "HUMAN", "align_status": "COMPLETED"},
        )

        # The tab links used to be hand-built hrefs that carried only batch_prefix, so
        # clicking a family quietly widened the view back to the whole mirror.
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


# --- 2b. paging and sorting --------------------------------------------------------------


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


# --- 3. columns --------------------------------------------------------------------------


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


# --- 4. cart -----------------------------------------------------------------------------


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


# --- 5. checkout and submission -----------------------------------------------------------


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


# --- 6. queue and failures ----------------------------------------------------------------


class TestQueueAndFailures:
    def test_cancelling_a_pending_entry(self, logged_in, queued_entry):
        entry = queued_entry("READY-1")

        response = logged_in.post(reverse("web_ui:cancel", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert b"Cancelled READY-1" in response.content
        assert entry.status == QueueEntry.Status.CANCELLED

    def test_an_entry_already_on_its_way_to_ocs_cannot_be_cancelled(self, logged_in, queued_entry):
        entry = queued_entry("READY-1")
        QueueEntry.objects.filter(pk=entry.pk).update(status=QueueEntry.Status.SUBMITTING)

        response = logged_in.post(reverse("web_ui:cancel", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert b"already being submitted" in response.content
        assert entry.status == QueueEntry.Status.SUBMITTING

    def test_retrying_a_failed_entry_puts_it_back_on_the_queue(self, logged_in, queued_entry):
        entry = queued_entry("READY-1")
        QueueEntry.objects.filter(pk=entry.pk).update(
            status=QueueEntry.Status.FAILED, error_message="ocs exited 1"
        )

        listing = logged_in.get(reverse("web_ui:failed"))
        assert b"ocs exited 1" in listing.content

        response = logged_in.post(reverse("web_ui:retry", args=[entry.pk]), follow=True)

        entry.refresh_from_db()
        assert b"READY-1 is back on the queue" in response.content
        assert entry.status == QueueEntry.Status.PENDING
        assert entry.error_message == ""

    def test_deleting_a_failed_entry(self, logged_in, queued_entry):
        entry = queued_entry("READY-1")
        QueueEntry.objects.filter(pk=entry.pk).update(status=QueueEntry.Status.FAILED)

        response = logged_in.post(reverse("web_ui:delete-job", args=[entry.pk]), follow=True)

        assert b"Deleted the failed entry for READY-1" in response.content
        assert not QueueEntry.objects.filter(pk=entry.pk).exists()

    def test_delete_confirms_first_but_retry_does_not(self, logged_in, queued_entry):
        """Delete is irreversible; Retry is not, so only Delete asks first."""
        entry = queued_entry("READY-1")
        QueueEntry.objects.filter(pk=entry.pk).update(status=QueueEntry.Status.FAILED)

        response = logged_in.get(reverse("web_ui:failed"))
        text = response.content.decode()

        retry_button = text[
            text.index('aria-label="Retry') : text.index("</button>", text.index('aria-label="Retry'))
        ]
        delete_button = text[
            text.index('aria-label="Delete') : text.index("</button>", text.index('aria-label="Delete'))
        ]
        assert "onclick" not in retry_button
        assert "return confirm(" in delete_button

    def test_a_live_entry_cannot_be_deleted(self, logged_in, queued_entry):
        entry = queued_entry("READY-1")

        response = logged_in.post(reverse("web_ui:delete-job", args=[entry.pk]), follow=True)

        assert b"Only failed entries can be deleted" in response.content
        assert QueueEntry.objects.filter(pk=entry.pk).exists()


class TestOtherPeoplesJobs:
    """One user must not be able to see or touch another user's queue entry."""

    @pytest.fixture
    def theirs(self, other_client, active_config, make_sample, other_user):
        make_sample("THEIRS-1")
        other_client.post(reverse("web_ui:submit-confirm"), {"fastq_names": ["THEIRS-1"]})
        entry = QueueEntry.objects.get(sample__fastq_name="THEIRS-1")
        assert entry.requested_by == other_user
        return entry

    def test_it_is_not_on_your_queue_page(self, logged_in, theirs):
        assert logged_in.get(reverse("web_ui:queue")).context["entries"] == []

    def test_it_is_not_on_your_failures_page(self, logged_in, theirs):
        QueueEntry.objects.filter(pk=theirs.pk).update(status=QueueEntry.Status.FAILED)

        response = logged_in.get(reverse("web_ui:failed"))

        assert response.context["entries"] == []
        assert b"THEIRS-1" not in response.content

    def test_you_cannot_cancel_it(self, logged_in, theirs):
        response = logged_in.post(reverse("web_ui:cancel", args=[theirs.pk]))

        theirs.refresh_from_db()
        assert response.status_code == 404
        assert theirs.status == QueueEntry.Status.PENDING

    def test_you_cannot_retry_it(self, logged_in, theirs):
        QueueEntry.objects.filter(pk=theirs.pk).update(status=QueueEntry.Status.FAILED, error_message="x")

        response = logged_in.post(reverse("web_ui:retry", args=[theirs.pk]))

        theirs.refresh_from_db()
        assert response.status_code == 404
        assert theirs.status == QueueEntry.Status.FAILED
        assert theirs.error_message == "x"

    def test_you_cannot_delete_it(self, logged_in, theirs):
        QueueEntry.objects.filter(pk=theirs.pk).update(status=QueueEntry.Status.FAILED)

        response = logged_in.post(reverse("web_ui:delete-job", args=[theirs.pk]))

        assert response.status_code == 404
        assert QueueEntry.objects.filter(pk=theirs.pk).exists()


# --- 7. staff-only settings ----------------------------------------------------------------


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


# --- 8. CSV export ---------------------------------------------------------------------------


def csv_body(response) -> str:
    return b"".join(response.streaming_content).decode()


class TestCsvExport:
    def test_it_exports_what_the_filters_are_showing(self, logged_in, make_sample):
        make_sample("MOUSE-1", organism_common_name="mouse")
        make_sample("HUMAN-1", organism_common_name="human")

        response = logged_in.post(f"{reverse('web_ui:export')}?organism_common_name=human")

        body = csv_body(response)
        assert "HUMAN-1" in body and "MOUSE-1" not in body
        assert response["Content-Disposition"] == 'attachment; filename="omicshub-samples.csv"'

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


# --- 9. odd data and rough edges ------------------------------------------------------------


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
