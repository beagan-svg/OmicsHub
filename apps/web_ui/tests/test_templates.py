"""Template mistakes that render as visible text instead of failing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.urls import reverse

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def test_no_multiline_inline_comments():
    """`{# ... #}` is single-line only; spanning lines renders the comment to the page.

    It fails silently , no exception, just prose at the top of the page , so it is worth
    a test rather than an eye.
    """
    offenders = []
    for path in TEMPLATES.rglob("*.html"):
        text = path.read_text()
        for match in re.finditer(r"\{#", text):
            rest = text[match.start() :]
            close = rest.find("#}")
            if close != -1 and "\n" in rest[:close]:
                offenders.append(f"{path.name}:{text[: match.start()].count('\n') + 1}")

    assert not offenders, (
        f"Multi-line {{# #}} comments render as text; use {{% comment %}}: {', '.join(offenders)}"
    )


META_REFRESH = re.compile(r"<meta[^>]*http-equiv\s*=\s*[\"']?refresh", re.IGNORECASE)

#: The pages whose tables have been brought up to the accessibility bar. Kept explicit
#: rather than globbed so adding a template is a deliberate decision, not a silent pass.
CAPTIONED = [
    "queue.html",
    "failed_jobs.html",
    "workflow_manifests.html",
    "data_locations.html",
]
TABLE_TEMPLATES = [*CAPTIONED, "partials/job_monitor_tables.html"]


def test_no_blanket_meta_refresh():
    """A whole-document meta refresh loses scroll, focus and any open menu."""
    offenders = [path.name for path in TEMPLATES.rglob("*.html") if META_REFRESH.search(path.read_text())]
    assert not offenders, f"Blanket meta refresh found in: {', '.join(offenders)}"


def test_job_monitor_refreshes_tables_without_reloading_document():
    """Job Monitor polls its database fragment while keeping the page in place."""
    text = (TEMPLATES / "job_monitor.html").read_text()
    tables = (TEMPLATES / "partials/job_monitor_tables.html").read_text()
    assert "Sync monitor data from AWS" not in text
    assert 'aria-label="Sync running jobs from AWS"' in tables
    assert 'aria-label="Sync finished jobs from AWS"' in tables
    assert tables.count('include "partials/sync_status.html"') == 2
    assert tables.count('data-bs-placement="top"') == 2
    assert "initTooltips();" in text
    assert "setInterval(updateDurations, 1000)" in text
    assert "setInterval(refreshTables, 30000)" in text
    assert "window.location.reload" not in text


def test_job_monitor_has_a_running_stage_filter():
    text = (TEMPLATES / "partials/job_monitor_tables.html").read_text()
    assert 'aria-label="Filter running jobs by stage"' in text
    assert 'class="monitor-stage-filter__label"' not in text
    assert "{{ option.label }}" in text
    assert "running_stage_options" in text


def test_pages_poll_database_without_replacing_sample_interactions():
    dashboard = (TEMPLATES / "dashboard.html").read_text()
    locations = (TEMPLATES / "data_locations.html").read_text()
    cell = (TEMPLATES / "partials/sample_table_cell.html").read_text()
    queue = (TEMPLATES / "queue.html").read_text()
    failures = (TEMPLATES / "failed_jobs.html").read_text()
    base = (TEMPLATES / "base.html").read_text()

    assert "data-live-status-url=\"{% url 'web_ui:live-status' %}\"" in dashboard
    assert "data-live-status-url=\"{% url 'web_ui:live-status' %}\"" in locations
    assert "data-live-stage-status=" in cell
    assert "data-live-stage-status=" in locations
    assert 'id="queue-live-data" data-live-fragment' in queue
    assert 'id="failures-live-data" data-live-fragment' in failures
    assert "web_ui/js/live-status.js" in base
    assert "web_ui/js/live-fragments.js" in base
    fragments = (TEMPLATES.parent / "static/web_ui/js/live-fragments.js").read_text()
    assert "details[open]" in fragments
    assert "detail.open = true" in fragments
    assert 'data-live-detail="{{ entry.sample.fastq_name }}"' in queue


def test_job_monitor_demand_ids_are_copyable():
    text = (TEMPLATES / "partials/job_monitor_tables.html").read_text()
    assert '{% include "partials/copy_value.html" with value=row.demand_id label="Demand ID" %}' in text
    assert "data-copy-demand-id" not in text
    assert "navigator.clipboard.writeText" not in text
    assert ">Duration<" in text


def test_data_location_download_uses_the_native_form():
    """The S3 download submits one form so the browser can stream the ZIP."""
    text = (TEMPLATES / "data_locations.html").read_text()
    assert "form.submit()" in text
    assert "errorMessage" not in text


def test_copy_component_uses_one_clipboard_path():
    text = (TEMPLATES / "base.html").read_text()
    assert "navigator.clipboard.writeText" in text
    assert "execCommand" not in text


def test_every_table_has_a_caption():
    """A caption is what names a table to a screen reader before it is read out."""
    for name in TABLE_TEMPLATES:
        text = (TEMPLATES / name).read_text()
        tables = text.count("<table")
        captions = text.count("<caption")
        assert tables and captions == tables, f"{name}: {tables} table(s) but {captions} caption(s)"


def test_table_headers_carry_scope():
    """Without `scope`, a screen reader has to guess which cells a `th` heads."""
    for name in TABLE_TEMPLATES:
        text = (TEMPLATES / name).read_text()
        bare = re.findall(r"<th(?=[\s>])(?![^>]*\bscope=)[^>]*>", text)
        assert not bare, f"{name}: <th> without scope: {bare}"


def test_row_actions_name_the_job_they_act_on():
    """A column of buttons all reading Delete names nothing; the label says what it deletes."""
    failed = (TEMPLATES / "failed_jobs.html").read_text()
    assert 'aria-label="Delete {{ entry.stage }} job for {{ entry.sample.fastq_name }}"' in failed
    assert 'aria-label="Retry {{ entry.stage }} for {{ entry.sample.fastq_name }}"' in failed

    queue = (TEMPLATES / "queue.html").read_text()
    assert 'aria-label="Delete {{ entry.stage }} for {{ entry.sample.fastq_name }}"' in queue

    configs = (TEMPLATES / "workflow_manifests.html").read_text()
    assert 'aria-label="Activate {{ config.name }}"' in configs


def test_decorative_icons_are_hidden_from_assistive_tech():
    """A Bootstrap icon is a font glyph; unhidden it is announced as junk before the label."""
    for name in CAPTIONED:
        text = (TEMPLATES / name).read_text()
        exposed = re.findall(r'<i class="bi[^"]*"(?![^>]*aria-hidden)[^>]*>', text)
        assert not exposed, f"{name}: decorative icon without aria-hidden: {exposed}"


def test_exactly_one_h1_per_page():
    """Screen-reader users jump by heading; a page with none has no landmark to jump to."""
    for name in CAPTIONED:
        text = (TEMPLATES / name).read_text()
        assert text.count("<h1") == 1, f"{name} must have exactly one <h1>"


# --- app shell and dashboard -----------------------------------------------------------
# These assert against the *rendered* page rather than the template source: the dashboard's
# filter controls are generated in loops, so only the response says whether every one of
# them came out with a name attached.

SHELL = ["base.html", "dashboard.html"]


@pytest.fixture
def dashboard_html(client, user):
    client.force_login(user)
    return client.get(reverse("web_ui:dashboard")).content.decode()


def test_skip_link_targets_the_main_landmark(dashboard_html):
    """A long nav ahead of a 50-row table is what makes the skip link the top fix.

    A link pointing at an id that does not exist is worse than none, so both halves are
    asserted together , and `tabindex="-1"` is what makes the jump move focus, not just
    the scroll position.
    """
    assert '<a class="visually-hidden-focusable" href="#main-content">' in dashboard_html
    assert re.search(r'<main[^>]*\bid="main-content"[^>]*>', dashboard_html), (
        "skip link target must be the <main> landmark"
    )
    assert re.search(r'<main[^>]*\btabindex="-1"', dashboard_html)


def test_every_dashboard_filter_control_has_a_label(dashboard_html):
    """Placeholders and floating `<label>`s without `for` are decoration, not names.

    The advanced-filter labels all read correctly on screen but pointed at nothing, and the
    search box had only a placeholder , which vanishes the moment anything is typed.
    """
    labelled = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', dashboard_html))

    named = re.findall(
        r'<(?:select|input)\b(?![^>]*type="(?:hidden|checkbox|submit)")[^>]*\bid="([^"]+)"',
        dashboard_html,
    )
    assert named, "expected the dashboard to render text inputs and selects"

    unlabelled = sorted(set(named) - labelled)
    assert not unlabelled, f"controls with no <label for=...>: {unlabelled}"


def test_messages_container_is_a_polite_live_region(client, user):
    """Django injects messages on render; without a live region nothing is announced.

    The region has to be the container, not the alert: the container is what survives from
    one render to the next, so an added message reads as a change to it.
    """
    client.force_login(user)
    response = client.post(reverse("web_ui:sync"), {"batch_name_from_vendor": ""}, follow=True)
    html = response.content.decode()

    assert re.search(
        r'<div aria-live="polite">\s*<div class="alert alert-danger[^"]*">\s*'
        r"Enter a batch name to sync\.",
        html,
    ), "the message must render inside the aria-live container, not beside it"
    assert 'role="alert"' not in html, (
        "an assertive role nested in a polite region contradicts it; keep one live region"
    )


def test_active_nav_item_is_not_signalled_by_colour_alone(dashboard_html):
    """`.active` is a colour change and nothing else , aria-current is the audible half."""
    active_links = re.findall(r'<a class="nav-link active"[^>]*>', dashboard_html)
    assert len(active_links) == 1, f"expected one active nav item, got {active_links}"
    assert 'aria-current="page"' in active_links[0]


def test_shell_icons_are_hidden_and_toggles_expose_their_state():
    """Icon fonts announce as junk, and a toggle with no aria-expanded reads as a dead end."""
    for name in SHELL:
        text = (TEMPLATES / name).read_text()
        exposed = re.findall(r'<i class="bi[^"]*"(?![^>]*aria-hidden)[^>]*>', text)
        assert not exposed, f"{name}: decorative icon without aria-hidden: {exposed}"

    # Asserted attribute by attribute rather than as one literal string: the order they
    # are written in carries no meaning, and a formatter reordering two of them is not a
    # regression this test should report.
    base = (TEMPLATES / "base.html").read_text()
    toggle = re.search(r"<button[^>]*navbar-toggler[^>]*>", base)
    assert toggle, "no navbar toggle button"
    for attribute in ('aria-controls="nav"', 'aria-expanded="false"', "aria-label="):
        assert attribute in toggle.group(), f"navbar toggle is missing {attribute}"

    dashboard = (TEMPLATES / "dashboard.html").read_text()
    filters = re.search(r'<button[^>]*aria-controls="advanced-filters"[^>]*>', dashboard)
    assert filters, "no advanced-filters toggle"
    assert "aria-expanded=" in filters.group()

    menu = (TEMPLATES / "partials/column_menu.html").read_text()
    dropdown = re.search(r'<button[^>]*data-bs-toggle="dropdown"[^>]*>', menu)
    assert dropdown, "no column-menu dropdown toggle"
    for attribute in ('data-bs-auto-close="outside"', 'aria-expanded="false"'):
        assert attribute in dropdown.group(), f"column menu is missing {attribute}"


def test_more_filters_use_the_page_apply_button():
    """The advanced panel edits fields; the page toolbar submits them."""
    filters = (TEMPLATES / "partials/sample_advanced_filters.html").read_text()
    assert ">Apply filters<" not in filters
    for name in ("dashboard.html", "data_locations.html"):
        text = (TEMPLATES / name).read_text()
        assert text.count(">Apply filters<") == 1, name


def test_dashboard_table_is_captioned_and_scoped(dashboard_html):
    """A wide table needs to name itself, and every `th` needs to say what it heads."""
    assert re.search(r'<caption class="visually-hidden">', dashboard_html)
    bare = re.findall(r"<th(?=[\s>])(?![^>]*\bscope=)[^>]*>", dashboard_html)
    assert not bare, f"<th> without scope: {bare}"
