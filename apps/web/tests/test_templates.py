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
    "web/job_monitor.html",
    "web/queue.html",
    "web/failed_jobs.html",
    "web/configs.html",
]


def test_no_blanket_meta_refresh():
    """A whole-document meta refresh loses scroll, focus and any open menu.

    Job Monitor used to carry `content="60"`. Auto-refresh now lives in JS that skips
    hidden tabs and restores scroll, so no template should reintroduce the meta tag.
    """
    offenders = [path.name for path in TEMPLATES.rglob("*.html") if META_REFRESH.search(path.read_text())]
    assert not offenders, f"Blanket meta refresh found in: {', '.join(offenders)}"


def test_job_monitor_refresh_is_visibility_aware():
    """The replacement must actually be conditional, not a bare setInterval + reload."""
    text = (TEMPLATES / "web/job_monitor.html").read_text()
    assert "visibilityState" in text, "auto-refresh must skip tabs that are not visible"
    assert "sessionStorage" in text and "window.scrollY" in text, (
        "auto-refresh must stash scroll position before reloading"
    )
    assert 'id="refresh-toggle"' in text, "auto-refresh must be pausable"


def test_every_table_has_a_caption():
    """A caption is what names a table to a screen reader before it is read out."""
    for name in CAPTIONED:
        text = (TEMPLATES / name).read_text()
        tables = text.count("<table")
        captions = text.count("<caption")
        assert tables and captions == tables, f"{name}: {tables} table(s) but {captions} caption(s)"


def test_table_headers_carry_scope():
    """Without `scope`, a screen reader has to guess which cells a `th` heads."""
    for name in CAPTIONED:
        text = (TEMPLATES / name).read_text()
        bare = re.findall(r"<th(?=[\s>])(?![^>]*\bscope=)[^>]*>", text)
        assert not bare, f"{name}: <th> without scope: {bare}"


def test_row_actions_name_the_job_they_act_on():
    """A column of buttons all reading Delete names nothing; the label says what it deletes."""
    failed = (TEMPLATES / "web/failed_jobs.html").read_text()
    assert 'aria-label="Delete {{ entry.stage }} job for {{ entry.sample.fastq_name }}"' in failed
    assert 'aria-label="Retry {{ entry.stage }} for {{ entry.sample.fastq_name }}"' in failed

    queue = (TEMPLATES / "web/queue.html").read_text()
    assert 'aria-label="Cancel {{ entry.stage }} for {{ entry.sample.fastq_name }}"' in queue

    configs = (TEMPLATES / "web/configs.html").read_text()
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

SHELL = ["web/base.html", "web/dashboard.html"]


@pytest.fixture
def dashboard_html(client, user):
    client.force_login(user)
    return client.get(reverse("web:dashboard")).content.decode()


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
    response = client.post(reverse("web:sync"), {"batch_name_from_vendor": ""}, follow=True)
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
    base = (TEMPLATES / "web/base.html").read_text()
    toggle = re.search(r"<button[^>]*navbar-toggler[^>]*>", base)
    assert toggle, "no navbar toggle button"
    for attribute in ('aria-controls="nav"', 'aria-expanded="false"', "aria-label="):
        assert attribute in toggle.group(), f"navbar toggle is missing {attribute}"

    dashboard = (TEMPLATES / "web/dashboard.html").read_text()
    filters = re.search(r'<button[^>]*aria-controls="advanced-filters"[^>]*>', dashboard)
    assert filters, "no advanced-filters toggle"
    assert "aria-expanded=" in filters.group()

    menu = (TEMPLATES / "web/_column_menu.html").read_text()
    dropdown = re.search(r'<button[^>]*data-bs-toggle="dropdown"[^>]*>', menu)
    assert dropdown, "no column-menu dropdown toggle"
    for attribute in ('data-bs-auto-close="outside"', 'aria-expanded="false"'):
        assert attribute in dropdown.group(), f"column menu is missing {attribute}"


def test_dashboard_table_is_captioned_and_scoped(dashboard_html):
    """A wide table needs to name itself, and every `th` needs to say what it heads."""
    assert re.search(r'<caption class="visually-hidden">', dashboard_html)
    bare = re.findall(r"<th(?=[\s>])(?![^>]*\bscope=)[^>]*>", dashboard_html)
    assert not bare, f"<th> without scope: {bare}"
