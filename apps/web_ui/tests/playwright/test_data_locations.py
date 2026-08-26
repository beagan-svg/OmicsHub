"""Browser checks for the Data Locations table."""

import pytest

from apps.sample_catalog.models import Stage

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def data_location_page(page, live_server, user, make_sample, monkeypatch):
    sample = make_sample("PW-LOCATION-1", align="COMPLETED")
    sample.stage_statuses.filter(stage=Stage.ALIGN).update(file_store_id="store-1")
    monkeypatch.setattr(
        "apps.web_ui.data_location_queries.dynamodb.get_file_stores",
        lambda ids: {"store-1": {"file_store_id": "store-1", "s3_uri": "s3://bucket/results"}},
    )

    page.goto(f"{live_server.url}/accounts/login/")
    page.fill('input[name="username"]', user.username)
    page.fill('input[name="password"]', "password")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/**")
    page.goto(f"{live_server.url}/data-locations/?fastq_name={sample.fastq_name}")
    return page


def test_contents_tooltip_only_shows_while_hovering(data_location_page):
    page = data_location_page
    page.route(
        "**/contents/**",
        lambda route: route.fulfill(status=200, content_type="text/html", body="<p>Contents</p>"),
    )

    button = page.locator(".location-contents-toggle")

    def tooltip_style(property_name):
        return button.evaluate(
            "(element, propertyName) => getComputedStyle(element, '::after')[propertyName]",
            property_name,
        )

    assert tooltip_style("visibility") == "hidden"
    button.hover()
    assert tooltip_style("visibility") == "visible"
    assert tooltip_style("content") == '"View contents"'
    assert tooltip_style("right") == "0px"

    button.click()
    assert button.get_attribute("aria-expanded") == "true"
    assert tooltip_style("content") == '"Hide contents"'
    page.get_by_role("heading", name="Data Locations").hover()

    assert button.evaluate("element => document.activeElement === element")
    assert tooltip_style("visibility") == "hidden"
    assert page.locator(".tooltip.show").count() == 0


def test_contents_column_has_a_fixed_compact_width(data_location_page):
    page = data_location_page
    header = page.locator("th.location-contents-column")
    cell = page.locator("td.location-contents-column").filter(has=page.locator("button"))
    assert header.bounding_box()["width"] == pytest.approx(96, abs=1)
    assert cell.bounding_box()["width"] == pytest.approx(96, abs=1)
