"""Stage timings and demand ids , the fields the dashboard reports a run's cost from.

These tests cover two previous failures: the registry projection omitted `start_time` and
`duration`, and DynamoDB returned `Decimal` values for integer columns.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from apps.ocs_integration import dynamodb
from apps.sample_catalog import ocs_sync as sync
from apps.sample_catalog.models import Sample, Stage, StageStatus

pytestmark = pytest.mark.django_db


def create_sample(fastq_name="NW-MX32013-1") -> Sample:
    # Named apart from the root conftest's `make_sample` fixture, which it used to shadow.
    return Sample.objects.create(
        fastq_name=fastq_name,
        batch_name_from_vendor="MTX-32013",
        organism_common_name="mouse",
        library_prep_method_name="10xRSeq_Mult",
    )


def demand(demand_id="d-1", stage="align", **overrides) -> dict:
    """A demand-registry item shaped exactly as DynamoDB returns one."""
    item = {
        "demand_id": demand_id,
        "demand_type": stage,
        "status": "COMPLETED",
        "start_time": "2024-12-10T23:13:20.419900+00:00",
        "last_update_time": "2024-12-11T02:01:42.393491+00:00",
        # DynamoDB numbers deserialise as Decimal, never int.
        "duration": Decimal("10102"),
    }
    item.update(overrides)
    return item


class TestProjection:
    def test_the_registry_scan_asks_for_the_timing_fields(self, monkeypatch):
        """The original defect: these were absent, so the values never left AWS.

        Asserted against the projection string because that is the thing that was wrong ,
        a test on the parsed output would pass against a mock while production returned
        rows with no timings in them.
        """
        captured = {}

        def fake_scan(table_name, page_size, **kwargs):
            captured.update(kwargs)
            return iter([])

        monkeypatch.setattr(dynamodb, "_scan", fake_scan)
        list(dynamodb.scan_demands())

        projection = captured["ProjectionExpression"]
        assert "start_time" in projection
        assert "#d" in projection
        # "duration" is a DynamoDB reserved word, so it can only appear via the alias.
        assert captured["ExpressionAttributeNames"]["#d"] == "duration"


class TestParsing:
    def test_decimal_duration_becomes_an_int(self):
        assert sync._duration_seconds(demand()) == 10102
        assert isinstance(sync._duration_seconds(demand()), int)

    def test_a_missing_duration_is_none_not_zero(self):
        """A running stage has no duration; zero would claim it finished instantly."""
        item = demand()
        del item["duration"]

        assert sync._duration_seconds(item) is None

    def test_a_negative_duration_is_dropped(self):
        """Clock skew at OCS produces these; the column is unsigned."""
        assert sync._duration_seconds(demand(duration=Decimal("-5"))) is None

    def test_an_unparseable_duration_is_dropped_rather_than_raising(self):
        assert sync._duration_seconds(demand(duration="not a number")) is None

    def test_a_missing_start_time_is_none(self):
        """Demands predating the field carry no start_time."""
        item = demand()
        del item["start_time"]

        assert sync._optional_time(item, "start_time") is None

    def test_start_time_parses_to_an_aware_datetime(self):
        parsed = sync._optional_time(demand(), "start_time")

        assert parsed == dt.datetime(2024, 12, 10, 23, 13, 20, 419900, tzinfo=dt.UTC)
        assert parsed.tzinfo is not None


class TestStoredValues:
    def test_the_model_keeps_seconds_and_formats_for_reading(self):
        sample = create_sample()
        record = StageStatus.objects.create(
            sample=sample,
            stage=Stage.ALIGN,
            status="COMPLETED",
            demand_id="d-1",
            duration_seconds=10102,
        )

        assert record.duration_seconds == 10102
        assert record.duration_display == "2h 48m"

    @pytest.mark.parametrize(
        ("seconds", "shown"),
        [(0, "0m"), (45, "0m"), (90, "1m"), (3600, "1h"), (10102, "2h 48m"), (190800, "2d 5h")],
    )
    def test_duration_display_across_the_range(self, seconds, shown):
        record = StageStatus(duration_seconds=seconds)

        assert record.duration_display == shown

    def test_no_duration_displays_as_blank_not_zero(self):
        assert StageStatus(duration_seconds=None).duration_display == ""

    def test_the_file_store_accessor_returns_per_stage_values(self):
        sample = create_sample()
        StageStatus.objects.create(
            sample=sample,
            stage=Stage.INGEST,
            status="COMPLETED",
            file_store_id="a86dcdfc0ce54e2fb16740a83131da36ae47976d",
        )
        StageStatus.objects.create(
            sample=sample,
            stage=Stage.ALIGN,
            status="COMPLETED",
            file_store_id="b2b794e49df38f84a0271a2d76707b74beb80eb7",
        )
        sample = Sample.objects.prefetch_related("stage_statuses").get(pk=sample.pk)

        assert sample.stage_file_store_id(Stage.INGEST) == "a86dcdfc0ce54e2fb16740a83131da36ae47976d"
        assert sample.stage_file_store_id(Stage.ALIGN) == "b2b794e49df38f84a0271a2d76707b74beb80eb7"
        # A stage OCS has no record of, and one that produced nothing, both read blank.
        assert sample.stage_file_store_id(Stage.POST_ALIGN) == ""

    def test_accessors_return_per_stage_values(self):
        sample = create_sample()
        StageStatus.objects.create(
            sample=sample,
            stage=Stage.INGEST,
            status="COMPLETED",
            demand_id="ingest-id",
            duration_seconds=60,
        )
        StageStatus.objects.create(
            sample=sample,
            stage=Stage.ALIGN,
            status="COMPLETED",
            demand_id="align-id",
            duration_seconds=7200,
        )
        sample = Sample.objects.prefetch_related("stage_statuses").get(pk=sample.pk)

        assert sample.stage_demand_id(Stage.INGEST) == "ingest-id"
        assert sample.stage_demand_id(Stage.ALIGN) == "align-id"
        assert sample.stage_duration(Stage.ALIGN) == "2h"
        assert sample.stage_duration_seconds(Stage.ALIGN) == 7200
        # A stage OCS has no record of reads blank rather than raising.
        assert sample.stage_duration(Stage.POST_ALIGN) == ""
        assert sample.stage_demand_id(Stage.POST_ALIGN) == ""

    def test_stage_accessors_do_not_query_per_call(self, django_assert_num_queries):
        """Three stage columns across fifty rows must not become 150 queries."""
        sample = create_sample()
        StageStatus.objects.create(
            sample=sample, stage=Stage.ALIGN, status="COMPLETED", demand_id="d", duration_seconds=1
        )
        loaded = Sample.objects.prefetch_related("stage_statuses").get(pk=sample.pk)

        with django_assert_num_queries(0):
            for _ in range(10):
                loaded.stage_status(Stage.ALIGN)
                loaded.stage_duration(Stage.ALIGN)
                loaded.stage_demand_id(Stage.ALIGN)
                loaded.stage_file_store_id(Stage.ALIGN)
