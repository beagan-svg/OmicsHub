"""Browser-level checks for the job-log credential panel and eye-icon log viewer.

Runs against pytest-django's live_server (a real HTTP server in this same test
process), driven by a real Chromium via pytest-playwright. AWS itself is monkeypatched
at the same apps.ocs_integration.log_credentials boundary the other test layers use --
no live credentials, and nothing here captures a screenshot or trace containing one.
"""

from __future__ import annotations

from threading import Event

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from apps.ocs_integration import log_credentials
from apps.sample_catalog.models import Stage

from ..conftest import stub_valid_sts

pytestmark = pytest.mark.django_db(transaction=True)

FAKE_ACCESS_KEY = "test-access-key"
FAKE_SECRET_KEY = "fake-secret-not-a-real-value-000000000000"
FAKE_SESSION_TOKEN = "fake-session-token-not-a-real-value"


def paste_block():
    """The literal export-statement shape AWS SSO/CLI output gives you -- what a reader
    actually pastes into the single textarea, not three separate values."""
    return (
        f'export AWS_ACCESS_KEY_ID="{FAKE_ACCESS_KEY}"\n'
        f'export AWS_SECRET_ACCESS_KEY="{FAKE_SECRET_KEY}"\n'
        f'export AWS_SESSION_TOKEN="{FAKE_SESSION_TOKEN}"\n'
    )


def login(page, live_server, username, password):
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/**")


def open_credentials(page):
    toggle = page.locator("[data-job-log-credentials-toggle]")
    if toggle.get_attribute("aria-expanded") == "false":
        toggle.click()


@pytest.fixture
def running_demand(make_sample):
    sample = make_sample("PW-RUN-1", align="IN_PROGRESS")
    return sample.stage_statuses.get(stage=Stage.ALIGN).demand_id


@pytest.fixture
def finished_demand(make_sample):
    sample = make_sample("PW-FINISHED-1", align="COMPLETED")
    return sample.stage_statuses.get(stage=Stage.ALIGN).demand_id


@pytest.fixture
def credentials_form(live_server, user, running_demand, page):
    login(page, live_server, user.username, "password")
    page.goto(f"{live_server.url}/monitor/")
    page.wait_for_selector("#job-log-credentials")
    return page


@pytest.fixture
def finished_credentials_form(live_server, user, finished_demand, page):
    login(page, live_server, user.username, "password")
    page.goto(f"{live_server.url}/monitor/")
    page.wait_for_selector("#job-log-credentials")
    return page


class TestCredentialsRequiredState:
    def test_eye_icon_is_disabled_before_credentials_are_provided(self, credentials_form):
        toggle = credentials_form.locator("[data-job-log-toggle]").first
        assert toggle.is_disabled()
        assert (
            credentials_form.locator("[data-job-log-credentials-status-pill]").inner_text()
            == "Credentials required"
        )

    def test_no_network_request_is_possible_on_a_disabled_toggle(self, credentials_form):
        """A disabled <button> cannot dispatch a click event at all in a real browser --
        this is the "functionally disabled, not just visually" requirement, verified by
        the browser's own actionability model rather than asserted in isolation."""
        requests = []
        credentials_form.on("request", lambda request: requests.append(request.url))
        toggle = credentials_form.locator("[data-job-log-toggle]").first

        with pytest.raises(PlaywrightTimeoutError):
            toggle.click(timeout=1000)

        assert not any("/logs/" in url for url in requests)


class TestFullCredentialFlow:
    def test_validate_then_expand_then_clear(self, credentials_form, monkeypatch, running_demand):
        stub_valid_sts(monkeypatch)
        monkeypatch.setattr(
            log_credentials,
            "fetch_job_logs",
            lambda request, demand_id, execution_arn, **kwargs: [
                {"timestamp": 1700000000000, "message": "hello from the fake job"}
            ],
        )

        page = credentials_form
        open_credentials(page)
        assert page.get_by_role("button", name="Validate credentials").is_visible()
        assert page.get_by_role("button", name="Replace").count() == 0
        page.fill("#jlc-paste", paste_block())
        page.click("[data-job-log-credentials-submit]")

        page.wait_for_selector('[data-job-log-credentials-status-pill]:has-text("Credentials valid")')
        assert page.locator("[data-job-log-credentials-account]").inner_text() == "123456789012"
        assert "Cannot be determined" in page.locator("[data-job-log-credentials-expiry]").inner_text()
        assert not page.get_by_role("button", name="Validate credentials").is_visible()

        credentials_toggle = page.locator("[data-job-log-credentials-toggle]")
        credentials_icon = page.locator("[data-job-log-credentials-icon]")
        assert credentials_toggle.get_attribute("aria-expanded") == "true"
        assert "bi-eye" in (credentials_icon.get_attribute("class") or "")
        credentials_toggle.click()
        assert credentials_toggle.get_attribute("aria-expanded") == "false"
        page.wait_for_function(
            "document.querySelector('[data-job-log-credentials-icon]').classList.contains('bi-eye-slash')"
        )
        assert "bi-eye-slash" in (credentials_icon.get_attribute("class") or "")
        assert credentials_toggle.get_attribute("aria-label") == "Expand the AWS credentials panel"
        credentials_toggle.click()
        assert credentials_toggle.get_attribute("aria-expanded") == "true"
        page.wait_for_function(
            "document.querySelector('[data-job-log-credentials-icon]').classList.contains('bi-eye')"
        )

        # The eye icon only becomes enabled once credentials are valid -- this is the
        # "log viewer must remain disabled until credentials are provided" requirement,
        # checked at the point where it flips, not only at the start.
        toggle = page.locator("[data-job-log-toggle]").first
        assert not toggle.is_disabled()

        toggle.click()
        page.wait_for_selector(".job-log-viewer")
        assert "hello from the fake job" in page.locator(".job-log-viewer").inner_text()
        # Starts at the top (the oldest visible line), not scrolled to the bottom.
        assert page.evaluate("document.querySelector('.job-log-viewer').scrollTop") == 0

    def test_open_panel_re_fetches_after_a_poll_refresh_instead_of_reverting(
        self, credentials_form, monkeypatch, running_demand
    ):
        """A table poll keeps the old logs visible until refreshed logs arrive."""
        stub_valid_sts(monkeypatch)
        first_request_started = Event()
        retry_started = Event()
        release_requests = Event()
        requests = 0

        def fetch_logs(request, demand_id, execution_arn, **kwargs):
            nonlocal requests
            requests += 1
            if requests == 1:
                first_request_started.set()
            else:
                retry_started.set()
            release_requests.wait(timeout=5)
            return [{"timestamp": 1700000001000, "message": "refreshed logs"}]

        monkeypatch.setattr(log_credentials, "fetch_job_logs", fetch_logs)
        page = credentials_form
        open_credentials(page)
        page.fill("#jlc-paste", paste_block())
        page.click("[data-job-log-credentials-submit]")
        page.wait_for_selector('[data-job-log-credentials-status-pill]:has-text("Credentials valid")')

        toggle = page.locator("[data-job-log-toggle]").first
        toggle.click()
        assert first_request_started.wait(timeout=2)
        page.locator("[data-job-log-body]").first.evaluate(
            "body => { body.innerHTML = '<div class=\"job-log-viewer\">preserved logs</div>'; }"
        )

        page.evaluate("""
            async () => {
                const region = document.getElementById('monitor-live-data');
                const openPanels = [...region.querySelectorAll('[data-job-log-panel][data-open="true"]')]
                    .map((p) => ({
                        demandId: p.dataset.demandId,
                        body: p.querySelector('[data-job-log-body]').innerHTML,
                    }));
                const response = await fetch(window.location.href, {
                    headers: {"X-Requested-With": "XMLHttpRequest"},
                });
                region.dispatchEvent(new CustomEvent('joblog:before-refresh', {bubbles: true}));
                region.innerHTML = await response.text();
                openPanels.forEach(({demandId, body}) => {
                    const panel = region.querySelector(`[data-job-log-panel][data-demand-id="${demandId}"]`);
                    const toggle = region.querySelector(
                        `[data-job-log-toggle][data-demand-id="${demandId}"]`
                    );
                    if (panel) {
                        panel.dataset.open = "true";
                        panel.querySelector('[data-job-log-body]').innerHTML = body;
                    }
                    if (toggle) toggle.setAttribute('aria-expanded', 'true');
                });
                region.dispatchEvent(new CustomEvent('joblog:refreshed', {bubbles: true}));
            }
        """)

        assert retry_started.wait(timeout=2)
        assert "preserved logs" in page.locator(".job-log-viewer").inner_text()
        assert "Loading…" not in page.locator("[data-job-log-body]").first.inner_text()
        release_requests.set()
        page.wait_for_selector(".job-log-viewer:has-text('refreshed logs')")
        assert "Provide AWS credentials" not in page.content()

    def test_eye_icon_still_opens_after_the_table_html_is_replaced(self, credentials_form, monkeypatch):
        """Regression test for two bugs, found together: job_monitor.html's own
        30-second poll (and live-fragments.js, for the Failures page) replaces
        #monitor-live-data's innerHTML wholesale. That used to (1) leave freshly-
        rendered eye icons with no open/close listener at all, because disclosure.js
        bound one listener per element, once, at page load, and (2) even once (1) was
        fixed, leave them with no fetch-triggering listener either, because
        job-log-credentials.js's own "already bound" guard was a `data-job-log-bound`
        HTML attribute -- which *does* survive an innerHTML round trip, even though the
        addEventListener it was guarding does not, so the guard read a stale "yes" on a
        node that in fact had no listener. Clicking did nothing, forever, after the
        first poll, either way. Forcing the same replacement here (rather than waiting a
        real 30 seconds) reproduces the exact condition that broke both.
        """
        stub_valid_sts(monkeypatch)
        monkeypatch.setattr(
            log_credentials,
            "fetch_job_logs",
            lambda request, demand_id, execution_arn, **kwargs: [
                {"timestamp": 1700000000000, "message": "still here after a refresh"}
            ],
        )
        page = credentials_form
        open_credentials(page)
        page.fill("#jlc-paste", paste_block())
        page.click("[data-job-log-credentials-submit]")
        page.wait_for_selector('[data-job-log-credentials-status-pill]:has-text("Credentials valid")')

        # Matches exactly what job_monitor.html's own 30-second refreshTables() and
        # live-fragments.js's refresh() both do: replace the region's innerHTML, then
        # dispatch joblog:refreshed so job-log-credentials.js re-binds/re-enables
        # whatever's now in the DOM. Skipping the dispatch here would test an incomplete
        # simulation of the refresh, not the real one.
        page.evaluate("""
            () => {
                const region = document.getElementById('monitor-live-data');
                region.innerHTML = region.innerHTML;
                region.dispatchEvent(new CustomEvent('joblog:refreshed', {bubbles: true}));
            }
        """)

        toggle = page.locator("[data-job-log-toggle]").first
        assert not toggle.is_disabled()
        toggle.click()
        page.wait_for_selector(".job-log-viewer")
        assert "still here after a refresh" in page.locator(".job-log-viewer").inner_text()

        # Clearing must re-disable every eye icon on the page, immediately.
        page.click("[data-job-log-credentials-clear]")
        page.wait_for_selector('[data-job-log-credentials-status-pill]:has-text("Credentials required")')
        assert page.locator("[data-job-log-toggle]").first.is_disabled()

    def test_invalid_credentials_show_a_redacted_message_not_a_traceback(self, credentials_form, monkeypatch):
        def raise_invalid(request, a, s, t):
            raise log_credentials.CredentialError("InvalidClientTokenId", "AWS rejected these credentials.")

        monkeypatch.setattr(log_credentials, "validate_credentials", raise_invalid)

        page = credentials_form
        open_credentials(page)
        page.fill("#jlc-paste", paste_block())
        page.click("[data-job-log-credentials-submit]")

        page.wait_for_selector('[data-job-log-credentials-status-pill]:has-text("Credentials failed")')
        assert page.locator("[data-job-log-credentials-clear]").is_visible()
        assert page.locator("[data-job-log-credentials-status-pill]").get_attribute("title") == (
            "AWS rejected these credentials."
        )
        assert page.locator("[data-job-log-toggle]").first.is_disabled()
        page_text = page.content()
        assert FAKE_SECRET_KEY not in page_text
        assert "Traceback" not in page_text

    def test_expired_credentials_show_expired_status(self, credentials_form, monkeypatch):
        def raise_expired(request, access_key, secret_key, session_token):
            raise log_credentials.CredentialError("ExpiredToken", "These credentials have expired.")

        monkeypatch.setattr(log_credentials, "validate_credentials", raise_expired)

        page = credentials_form
        open_credentials(page)
        page.fill("#jlc-paste", paste_block())
        page.click("[data-job-log-credentials-submit]")

        page.wait_for_selector('[data-job-log-credentials-status-pill]:has-text("Credentials expired")')
        assert page.locator("[data-job-log-credentials-clear]").is_visible()
        assert page.locator("[data-job-log-credentials-status-pill]").get_attribute("title") == (
            "These credentials have expired."
        )


class TestResponsiveLayout:
    @pytest.mark.parametrize("width,height", [(1280, 900), (480, 850)])
    def test_credential_panel_does_not_overflow_the_viewport(self, credentials_form, width, height):
        """Scoped to the new credential panel, not document.body: the Running/Finished
        tables already push body.scrollWidth past the viewport on narrow screens before
        this feature touches anything (a pre-existing .card/.table-responsive flexbox
        sizing issue, confirmed via `git diff` against the pre-feature template -- the
        table overflows by ~570px even without the Logs column this feature adds).
        Fixing that is a separate, unrelated change; this test instead holds the one
        surface this feature owns to the bar the whole page should eventually meet.
        """
        page = credentials_form
        page.set_viewport_size({"width": width, "height": height})
        panel_box = page.locator("#job-log-credentials").bounding_box()
        assert panel_box["x"] >= 0
        assert panel_box["x"] + panel_box["width"] <= width + 5

    def test_paste_box_fits_within_a_narrow_viewport(self, credentials_form):
        page = credentials_form
        page.set_viewport_size({"width": 480, "height": 850})
        paste_box = page.locator("#jlc-paste").bounding_box()
        assert paste_box["x"] >= 0
        assert paste_box["x"] + paste_box["width"] <= 480 + 5

    def test_pasted_text_is_visually_masked(self, credentials_form):
        """-webkit-text-security masks the rendered glyphs, not the DOM value -- this
        confirms both halves: the real value is still there for parsing/submission, and
        the rendered text is not literally the pasted secret."""
        page = credentials_form
        open_credentials(page)
        page.fill("#jlc-paste", paste_block())
        assert page.locator("#jlc-paste").input_value() == paste_block()
        rendered = page.evaluate(
            "document.getElementById('jlc-paste').style.webkitTextSecurity "
            "|| getComputedStyle(document.getElementById('jlc-paste')).webkitTextSecurity"
        )
        # Firefox has no such property and returns "", which is the documented, accepted
        # fallback (plain text visible while still in the box) -- not a test failure.
        assert rendered in ("disc", "")


class TestMonitorTableLayout:
    @staticmethod
    def finished_table(page):
        return page.locator("#monitor-live-data .card").filter(has_text="Recently finished").first

    def test_closed_log_rows_do_not_create_empty_table_space(self, finished_credentials_form):
        page = finished_credentials_form
        finished_table = self.finished_table(page)
        closed_rows = finished_table.locator("tr.job-log-row")

        assert closed_rows.count() > 0
        for index in range(closed_rows.count()):
            assert closed_rows.nth(index).evaluate("row => getComputedStyle(row).display") == "none"

        table = finished_table.locator(".table-responsive")
        table_height = table.evaluate(
            "element => ({scrollHeight: element.scrollHeight, visibleRowsHeight: "
            "[...element.querySelectorAll('tbody tr:not(.job-log-row)')]"
            ".reduce((height, row) => height + row.getBoundingClientRect().height, 0), "
            "headerHeight: element.querySelector('thead').getBoundingClientRect().height})"
        )
        assert table_height["scrollHeight"] <= (
            table_height["visibleRowsHeight"] + table_height["headerHeight"] + 4
        )

    def test_log_actions_use_a_compact_centered_column(self, credentials_form):
        page = credentials_form
        headers = page.locator("th.monitor-logs-column:visible")
        cells = page.locator("tbody tr:not(.job-log-row) td.monitor-logs-column")

        assert headers.count() > 0
        assert cells.count() > 0
        for index in range(headers.count()):
            header_box = headers.nth(index).bounding_box()
            assert header_box["width"] == pytest.approx(64, abs=1)

        for index in range(cells.count()):
            cell_box = cells.nth(index).bounding_box()
            button_box = cells.nth(index).locator("button").bounding_box()
            assert cell_box["width"] == pytest.approx(64, abs=1)
            assert button_box["x"] + button_box["width"] / 2 == pytest.approx(
                cell_box["x"] + cell_box["width"] / 2,
                abs=1,
            )

    def test_hidden_log_tooltip_does_not_extend_the_table_scroll_area(self, credentials_form):
        wrapper = credentials_form.locator(".table-responsive:visible").first
        overflow = wrapper.evaluate("""element => {
            const tableWidth = element.querySelector('table').getBoundingClientRect().width;
            return element.scrollWidth - Math.ceil(tableWidth);
        }""")
        assert overflow <= 1

    def test_clicking_finished_status_does_not_navigate(self, finished_credentials_form):
        page = finished_credentials_form
        navigations = []
        page.on("framenavigated", lambda frame: navigations.append(frame.url))

        finished_table = self.finished_table(page)
        status = finished_table.locator("tbody tr:not(.job-log-row)").first.locator(".state")
        status.click()
        page.wait_for_timeout(100)

        assert page.url.endswith("/monitor/")
        assert navigations == []
