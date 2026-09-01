"""Cart contents, the checkout page, and cart-clearing on submission."""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

from apps.sample_catalog.models import NOT_COMPLETED
from apps.submission_queue.models import CartItem, QueueEntry

from .conftest import messages_in

pytestmark = pytest.mark.django_db


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

    def test_a_fastq_name_the_local_database_no_longer_holds_is_reported(self, logged_in, make_sample, user):
        make_sample("READY-1")

        response = logged_in.post(
            reverse("web_ui:cart-add"), {"fastq_names": ["READY-1", "GHOST-1"]}, follow=True
        )

        assert b"Added 1 sample to the cart" in response.content
        assert b"1 no longer exists in the local database" in response.content
        assert CartItem.objects.filter(user=user).count() == 1

    def test_a_cart_of_only_ghosts_says_so_rather_than_reporting_success(self, logged_in, user):
        response = logged_in.post(reverse("web_ui:cart-add"), {"fastq_names": ["GHOST-1"]}, follow=True)

        assert b"1 no longer exists in the local database" in response.content
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

    def test_a_sample_no_longer_in_the_local_database_is_reported(self, logged_in, make_sample):
        """A page open since before a re-sync can still list a sample that has since gone."""
        make_sample("READY-1")

        response = logged_in.post(
            reverse("web_ui:cart-add"), {"fastq_names": ["READY-1", "GONE-1"]}, follow=True
        )

        assert b"1 no longer exists in the local database" in response.content


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
