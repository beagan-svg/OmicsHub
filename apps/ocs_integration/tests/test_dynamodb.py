"""DynamoDB reads: table naming, pagination, and how history rows are parsed.

boto3 is replaced with a fake resource, so nothing here touches AWS.
"""

from __future__ import annotations

import pytest
from django.test import override_settings

from apps.ocs_integration import dynamodb


class FakeTable:
    def __init__(self, name, pages):
        self.name = name
        self.pages = list(pages)
        self.queries = []

    def query(self, **kwargs):
        self.queries.append(kwargs)
        return self.pages.pop(0)


class FakeResource:
    def __init__(self, pages=None, batch_responses=None):
        self.tables = {}
        self.pages = pages or []
        self.batch_responses = list(batch_responses or [])
        self.batch_requests = []

    def Table(self, name):  # noqa: N802 - boto3's API
        self.tables[name] = FakeTable(name, self.pages)
        return self.tables[name]

    def batch_get_item(self, RequestItems):  # noqa: N803 - boto3's API
        self.batch_requests.append(RequestItems)
        return self.batch_responses.pop(0)


class FakeSession:
    """Records how the session was built, so credential resolution can be asserted on."""

    built = []

    def __init__(self, resource, profile_name=None):
        self._resource = resource
        FakeSession.built.append({"profile_name": profile_name})

    def resource(self, service, region_name=None):
        self._resource.service = service
        self._resource.region_name = region_name
        return self._resource


@pytest.fixture(autouse=True)
def _no_cached_resource():
    """`_resource()` caches per thread, so a resource built by an earlier test would
    outlive that test's patched Session and serve the real client to this one."""
    dynamodb.reset_resource_cache()
    yield
    dynamodb.reset_resource_cache()


@pytest.fixture
def fake_boto(monkeypatch):
    FakeSession.built = []

    def _install(resource):
        monkeypatch.setattr(
            dynamodb.boto3,
            "Session",
            lambda profile_name=None: FakeSession(resource, profile_name=profile_name),
        )
        return resource

    return _install


@override_settings(OCS_ENV_BASE="prod")
def test_history_splits_the_demand_type_and_id(fake_boto):
    fake_boto(
        FakeResource(
            pages=[
                {
                    "Items": [
                        {
                            "demand_type_and_id": "align#0d1f-uuid",
                            "last_update_time": "2026-01-01T00:00:00Z",
                            "fastq_gfs_path": "gfs://a86dcdfc0ce54e2fb16740a83131da36ae47976d",
                            "input_output_gfs_pairs": [
                                {"outputs": ["gfs://b2b794e49df38f84a0271a2d76707b74beb80eb7"]}
                            ],
                        }
                    ]
                }
            ]
        )
    )

    assert dynamodb.get_history("NY-MX22068-2") == [
        {
            "demand_type": "align",
            "demand_id": "0d1f-uuid",
            "last_update_time": "2026-01-01T00:00:00Z",
            # See apps/sample_catalog/tests/test_file_store_ids.py for what the demand produced.
            # how this is picked out of a row with several outputs.
            "file_store_id": "b2b794e49df38f84a0271a2d76707b74beb80eb7",
        }
    ]


@override_settings(OCS_ENV_BASE="prod")
def test_history_reads_the_env_prefixed_table(fake_boto):
    resource = fake_boto(FakeResource(pages=[{"Items": []}]))

    dynamodb.get_history("NY-MX22068-2")

    assert "prod-fastq-history" in resource.tables


@override_settings(OCS_ENV_BASE="prod")
def test_batch_metadata_query_uses_the_vendor_batch_index(fake_boto):
    resource = fake_boto(FakeResource(pages=[{"Items": []}]))

    dynamodb.get_metadata_by_batch("MTX-22068")

    query = resource.tables["prod-fastq-metadata"].queries[0]
    assert query["IndexName"] == "prod-fastq-metadata-batch-name-from-vendor-index"


@override_settings(OCS_ENV_BASE="prod")
def test_queries_follow_pagination(fake_boto):
    fake_boto(
        FakeResource(
            pages=[
                {"Items": [{"fastq_name": "A"}], "LastEvaluatedKey": {"fastq_name": "A"}},
                {"Items": [{"fastq_name": "B"}]},
            ]
        )
    )

    entries = dynamodb.get_metadata_by_batch("MTX-22068")

    assert [entry["fastq_name"] for entry in entries] == ["A", "B"]


@override_settings(OCS_ENV_BASE="prod")
def test_in_progress_count_sums_every_page(fake_boto):
    resource = fake_boto(
        FakeResource(
            pages=[
                {"Count": 7, "LastEvaluatedKey": {"demand_id": "x"}},
                {"Count": 3},
            ]
        )
    )

    assert dynamodb.count_in_progress("align") == 10
    query = resource.tables["prod-demand-registry"].queries[0]
    assert query["IndexName"] == "prod-demand-registry-demand-type-start-time-index"
    assert query["Select"] == "COUNT"


@override_settings(OCS_ENV_BASE="prod")
def test_batch_get_retries_unprocessed_keys(fake_boto):
    """DynamoDB may return only part of a batch; the rest must still be fetched."""
    table = "prod-fastq-metadata"
    resource = fake_boto(
        FakeResource(
            batch_responses=[
                {
                    "Responses": {table: [{"fastq_name": "A"}]},
                    "UnprocessedKeys": {table: {"Keys": [{"fastq_name": "B"}]}},
                },
                {"Responses": {table: [{"fastq_name": "B"}]}},
            ]
        )
    )

    entries = dynamodb.get_metadata_by_fastq_names(["A", "B"])

    assert [entry["fastq_name"] for entry in entries] == ["A", "B"]
    assert len(resource.batch_requests) == 2


@override_settings(OCS_ENV_BASE="prod")
def test_unprocessed_keys_are_retried_with_growing_backoff(fake_boto, monkeypatch):
    """Unprocessed keys mean throttling, so retrying them flat out is how it gets worse."""
    sleeps = []
    monkeypatch.setattr(dynamodb.time, "sleep", sleeps.append)
    table = "prod-fastq-metadata"
    unprocessed = {"Responses": {table: []}, "UnprocessedKeys": {table: {"Keys": [{"fastq_name": "A"}]}}}
    done = {"Responses": {table: [{"fastq_name": "A"}]}}
    fake_boto(FakeResource(batch_responses=[unprocessed, unprocessed, done]))

    dynamodb.get_metadata_by_fastq_names(["A"])

    assert sleeps == [dynamodb.UNPROCESSED_BACKOFF, dynamodb.UNPROCESSED_BACKOFF * 2]


@override_settings(OCS_ENV_BASE="prod")
def test_batch_get_sends_each_key_once(fake_boto):
    """A repeated key makes DynamoDB reject the whole request, and demand ids repeat."""
    table = "prod-demand-registry"
    resource = fake_boto(
        FakeResource(batch_responses=[{"Responses": {table: [{"demand_id": "A"}, {"demand_id": "B"}]}}])
    )

    dynamodb.get_demands(["A", "B", "A"])

    assert resource.batch_requests[0][table]["Keys"] == [{"demand_id": "A"}, {"demand_id": "B"}]


@override_settings(OCS_ENV_BASE="prod", AWS_PROFILE="aibs-bicore", OCS_AWS_REGION="us-west-2")
def test_uses_the_configured_aws_profile(fake_boto):
    resource = fake_boto(FakeResource(pages=[{"Items": []}]))

    dynamodb.get_history("NY-MX22068-2")

    assert FakeSession.built == [{"profile_name": "aibs-bicore"}]
    assert resource.region_name == "us-west-2"


@override_settings(OCS_ENV_BASE="prod", AWS_PROFILE="")
def test_without_a_profile_boto_uses_its_default_chain(fake_boto):
    """Empty means "let boto3 decide" , env vars or the instance role, not a named profile."""
    fake_boto(FakeResource(pages=[{"Items": []}]))

    dynamodb.get_history("NY-MX22068-2")

    assert FakeSession.built == [{"profile_name": None}]


def test_batch_get_with_no_keys_makes_no_request(fake_boto):
    resource = fake_boto(FakeResource())

    assert dynamodb.get_metadata_by_fastq_names([]) == []
    assert resource.batch_requests == []
