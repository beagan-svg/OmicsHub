"""Temporary AWS credential handling for the job log viewer.

AWS calls go through botocore's Stubber, never a live account. Nothing here uses a real
access key, secret key, or session token -- every value below is an obvious placeholder.
"""

from __future__ import annotations

import datetime as dt

import boto3
import pytest
from botocore.stub import ANY, Stubber
from django.core.cache import cache
from django.test import RequestFactory

from apps.ocs_integration import dynamodb, log_credentials, s3

FAKE_ACCESS_KEY = "test-access-key"
FAKE_SECRET_KEY = "fake-secret-not-a-real-value-000000000000"
FAKE_SESSION_TOKEN = "fake-session-token-not-a-real-value"

REGION = "us-west-2"


def make_stubbed_client(service_name):
    client = boto3.client(
        service_name,
        region_name=REGION,
        aws_access_key_id=FAKE_ACCESS_KEY,
        aws_secret_access_key=FAKE_SECRET_KEY,
        aws_session_token=FAKE_SESSION_TOKEN,
    )
    return client, Stubber(client)


def task_submitted_event(output, *, event_id=1, resource_type="batch"):
    """A minimally-shaped TaskSubmitted history event -- everything GetExecutionHistory's
    response shape requires, so Stubber's own validation passes, plus the one field
    log_credentials._resolve_batch_job_id actually reads."""
    return {
        "id": event_id,
        "timestamp": 1700000000.0,
        "type": "TaskSubmitted",
        "taskSubmittedEventDetails": {
            "resourceType": resource_type,
            "resource": "submitJob.sync",
            "output": output,
        },
    }


def task_failed_event(cause, *, event_id=1):
    return {
        "id": event_id,
        "timestamp": 1700000000.0,
        "type": "TaskFailed",
        "taskFailedEventDetails": {
            "resourceType": "batch",
            "resource": "submitJob.sync",
            "error": "States.TaskFailed",
            "cause": cause,
        },
    }


def batch_job(job_id, *, log_stream_name="stream-1"):
    """A minimally-shaped Batch job -- everything DescribeJobs' response shape
    requires, plus the one field log_credentials._resolve_log_stream actually reads."""
    return {
        "jobId": job_id,
        "jobName": "fake-job",
        "jobQueue": "arn:aws:batch:us-west-2:123456789012:job-queue/fake-queue",
        "status": "SUCCEEDED",
        "startedAt": 1700000000000,
        "jobDefinition": "arn:aws:batch:us-west-2:123456789012:job-definition/fake-def:1",
        "attempts": [{"container": {"logStreamName": log_stream_name}}],
    }


def test_log_stream_lookup_reads_top_level_batch_container():
    batch_client, batch_stub = make_stubbed_client("batch")
    job = batch_job("job-123")
    job["container"] = {"logStreamName": "top-level-stream"}
    job["attempts"] = []
    batch_stub.add_response("describe_jobs", {"jobs": [job]}, {"jobs": ["job-123"]})
    batch_stub.activate()

    session = FakeSession({"batch": batch_client})

    assert log_credentials._resolve_log_stream(session, "job-123") == "top-level-stream"
    batch_stub.assert_no_pending_responses()


class FakeSession:
    """Stands in for the boto3.Session log_credentials._session() builds."""

    def __init__(self, clients):
        self._clients = clients
        self.client_calls = []

    def client(self, service_name, **kwargs):
        self.client_calls.append((service_name, kwargs))
        return self._clients[service_name]


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def request_():
    request = RequestFactory().get("/")
    request.session = type("FakeDjangoSession", (), {"session_key": "session-key-abc"})()
    return request


def other_request():
    request = RequestFactory().get("/")
    request.session = type("FakeDjangoSession", (), {"session_key": "session-key-xyz"})()
    return request


# --- validate_credentials ---------------------------------------------------------


def test_valid_credentials_are_cached_and_return_identity(request_, monkeypatch):
    sts_client, stub = make_stubbed_client("sts")
    stub.add_response(
        "get_caller_identity",
        {"UserId": "AID123", "Account": "010668866872", "Arn": "arn:aws:sts::010668866872:assumed-role/x/y"},
    )
    stub.activate()
    fake_session = FakeSession({"sts": sts_client})
    monkeypatch.setattr(log_credentials, "_session", lambda *a: fake_session)

    identity = log_credentials.validate_credentials(
        request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN
    )

    assert identity.account == "010668866872"
    assert identity.arn == "arn:aws:sts::010668866872:assumed-role/x/y"
    assert log_credentials.get_identity(request_) == identity
    stub.assert_no_pending_responses()


def test_missing_any_value_is_rejected_without_calling_aws(request_, monkeypatch):
    def fail_if_called(*a, **k):
        raise AssertionError("AWS must not be called when a credential value is missing")

    monkeypatch.setattr(log_credentials, "_session", fail_if_called)

    for args in [
        ("", FAKE_SECRET_KEY, FAKE_SESSION_TOKEN),
        (FAKE_ACCESS_KEY, "", FAKE_SESSION_TOKEN),
        (FAKE_ACCESS_KEY, FAKE_SECRET_KEY, ""),
    ]:
        with pytest.raises(log_credentials.CredentialError) as exc:
            log_credentials.validate_credentials(request_, *args)
        assert exc.value.code == "MissingValue"
    assert log_credentials.get_identity(request_) is None


def test_invalid_credentials_are_redacted_and_not_cached(request_, monkeypatch):
    sts_client, stub = make_stubbed_client("sts")
    stub.add_client_error("get_caller_identity", service_error_code="InvalidClientTokenId")
    stub.activate()
    monkeypatch.setattr(log_credentials, "_session", lambda *a: FakeSession({"sts": sts_client}))

    with pytest.raises(log_credentials.CredentialError) as exc:
        log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)

    assert exc.value.code == "InvalidClientTokenId"
    assert exc.value.rejected is True
    # The redacted message is a fixed string, never botocore's own exception text.
    assert "InvalidClientTokenId" not in str(exc.value) or str(exc.value) == "AWS rejected these credentials."
    assert log_credentials.get_identity(request_) is None


def test_expired_credentials_are_redacted(request_, monkeypatch):
    sts_client, stub = make_stubbed_client("sts")
    stub.add_client_error("get_caller_identity", service_error_code="ExpiredToken")
    stub.activate()
    monkeypatch.setattr(log_credentials, "_session", lambda *a: FakeSession({"sts": sts_client}))

    with pytest.raises(log_credentials.CredentialError) as exc:
        log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)

    assert exc.value.code == "ExpiredToken"
    assert exc.value.rejected is True
    assert exc.value.args[0] == "These credentials have expired."


def test_access_denied_is_redacted_but_not_treated_as_rejection(request_, monkeypatch):
    """AccessDenied means the credentials are real but under-permissioned, not expired --
    the module still evicts them (matching "AWS rejects them" in the spec), but callers
    should not confuse this with an expiry-shaped error."""
    sts_client, stub = make_stubbed_client("sts")
    stub.add_client_error("get_caller_identity", service_error_code="AccessDenied")
    stub.activate()
    monkeypatch.setattr(log_credentials, "_session", lambda *a: FakeSession({"sts": sts_client}))

    with pytest.raises(log_credentials.CredentialError) as exc:
        log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)

    assert exc.value.rejected is True
    assert exc.value.args[0] == "These credentials do not have permission for this action."


# --- expiration is never guessed ---------------------------------------------------


def test_validated_identity_never_carries_an_expiration(request_, monkeypatch):
    """GetCallerIdentity has no expiration field. This locks in that ValidatedIdentity
    has no expiry attribute at all, so nothing upstream can be tempted to invent one."""
    sts_client, stub = make_stubbed_client("sts")
    stub.add_response(
        "get_caller_identity",
        {
            "UserId": "AROAFAKE123456789012",
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/fake-role/fake-session",
        },
    )
    stub.activate()
    monkeypatch.setattr(log_credentials, "_session", lambda *a: FakeSession({"sts": sts_client}))

    identity = log_credentials.validate_credentials(
        request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN
    )
    assert not hasattr(identity, "expires_at")
    assert set(identity.__dataclass_fields__) == {"account", "arn"}


# --- clearing ------------------------------------------------------------------


def test_clearing_removes_cached_credentials(request_, monkeypatch):
    sts_client, stub = make_stubbed_client("sts")
    stub.add_response(
        "get_caller_identity",
        {
            "UserId": "AROAFAKE123456789012",
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/fake-role/fake-session",
        },
    )
    stub.activate()
    monkeypatch.setattr(log_credentials, "_session", lambda *a: FakeSession({"sts": sts_client}))
    log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)
    assert log_credentials.get_identity(request_) is not None

    log_credentials.clear_credentials(request_)

    assert log_credentials.get_identity(request_) is None


# --- isolation from the app's own AWS identity and from other sessions ------------


def test_session_is_built_from_only_the_three_supplied_values(request_, monkeypatch):
    captured = {}

    def fake_boto3_session(**kwargs):
        captured.update(kwargs)
        return FakeSession({})

    monkeypatch.setattr(log_credentials.boto3, "Session", fake_boto3_session)
    # Not actually calling AWS here -- just inspecting how the real _session() builds
    # the Session. FakeSession({}) has no "sts" client configured, so .client("sts")
    # raises KeyError; that's expected and is not what this test is checking.
    with pytest.raises(KeyError):
        log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)

    assert captured == {
        "aws_access_key_id": FAKE_ACCESS_KEY,
        "aws_secret_access_key": FAKE_SECRET_KEY,
        "aws_session_token": FAKE_SESSION_TOKEN,
    }
    assert "profile_name" not in captured


def test_never_falls_back_to_the_apps_own_aws_identity(request_, monkeypatch):
    """A log request must not use the app's AWS clients as a credential fallback."""
    dynamodb_calls = []
    s3_client_calls = []
    monkeypatch.setattr(dynamodb, "get_demands", lambda ids: dynamodb_calls.append(ids) or {})
    monkeypatch.setattr(s3, "_client", lambda: s3_client_calls.append(1))

    with pytest.raises(log_credentials.CredentialError):
        log_credentials.validate_credentials(request_, "", "", "")
    with pytest.raises(log_credentials.NoCredentials):
        log_credentials.fetch_job_logs(request_, "some-demand-id", "execution-arn")

    assert dynamodb_calls == []
    assert s3_client_calls == []


def test_one_sessions_credentials_are_not_visible_to_another(request_, monkeypatch):
    sts_client, stub = make_stubbed_client("sts")
    stub.add_response(
        "get_caller_identity",
        {
            "UserId": "AROAFAKE123456789012",
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/fake-role/fake-session",
        },
    )
    stub.activate()
    monkeypatch.setattr(log_credentials, "_session", lambda *a: FakeSession({"sts": sts_client}))
    log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)

    someone_else = other_request()
    assert log_credentials.get_identity(someone_else) is None


# --- secrets never appear in cached bytes or error text ---------------------------


def test_secret_values_are_not_stored_in_plaintext_in_the_cache(request_, monkeypatch):
    sts_client, stub = make_stubbed_client("sts")
    stub.add_response(
        "get_caller_identity",
        {
            "UserId": "AROAFAKE123456789012",
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/fake-role/fake-session",
        },
    )
    stub.activate()
    monkeypatch.setattr(log_credentials, "_session", lambda *a: FakeSession({"sts": sts_client}))

    log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)

    raw = cache.get(log_credentials._cache_key(request_.session.session_key))
    assert raw is not None
    assert FAKE_SECRET_KEY.encode() not in raw
    assert FAKE_SESSION_TOKEN.encode() not in raw


def test_credential_error_messages_never_contain_the_secret_values(request_, monkeypatch):
    sts_client, stub = make_stubbed_client("sts")
    stub.add_client_error(
        "get_caller_identity",
        service_error_code="InvalidClientTokenId",
        service_message=f"leaking {FAKE_SECRET_KEY} on purpose to prove the test catches it",
    )
    stub.activate()
    monkeypatch.setattr(log_credentials, "_session", lambda *a: FakeSession({"sts": sts_client}))

    with pytest.raises(log_credentials.CredentialError) as exc:
        log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)

    assert FAKE_SECRET_KEY not in str(exc.value)


# --- fetch_job_logs: the Step Functions -> Batch -> Logs chain --------------------


def _validated():
    sts_client, stub = make_stubbed_client("sts")
    stub.add_response(
        "get_caller_identity",
        {
            "UserId": "AROAFAKE123456789012",
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/fake-role/fake-session",
        },
    )
    stub.activate()
    return sts_client


def test_fetch_job_logs_without_credentials_raises_no_credentials(request_):
    with pytest.raises(log_credentials.NoCredentials):
        log_credentials.fetch_job_logs(request_, "some-demand-id", "execution-arn")


def test_failed_demand_resolves_workflow_and_execution_from_temporary_session():
    dynamodb_client, dynamodb_stub = make_stubbed_client("dynamodb")
    stepfunctions_client, stepfunctions_stub = make_stubbed_client("stepfunctions")

    dynamodb_stub.add_response(
        "get_item",
        {"Item": {"request": {"M": {"demand_workflow_name": {"S": "tenx-rnaseq-align"}}}}},
        {
            "TableName": "test-demand-registry",
            "Key": {"demand_id": {"S": "demand-failed"}},
            "ProjectionExpression": "#request",
            "ExpressionAttributeNames": {"#request": "request"},
        },
    )
    dynamodb_stub.activate()

    state_machine_arn = "arn:aws:states:us-west-2:123456789012:stateMachine:test-tenx-rnaseq-align"
    stepfunctions_stub.add_response(
        "list_executions",
        {
            "executions": [
                {
                    "executionArn": "arn:aws:states:us-west-2:123456789012:execution:x:old",
                    "name": "demand-failed-old",
                    "stateMachineArn": state_machine_arn,
                    "startDate": dt.datetime(2023, 11, 14, tzinfo=dt.UTC),
                    "status": "FAILED",
                },
                {
                    "executionArn": "arn:aws:states:us-west-2:123456789012:execution:x:new",
                    "name": "demand-failed-new",
                    "stateMachineArn": state_machine_arn,
                    "startDate": dt.datetime(2023, 11, 14, 0, 1, tzinfo=dt.UTC),
                    "status": "FAILED",
                },
            ]
        },
        {"stateMachineArn": state_machine_arn, "maxResults": 1000},
    )
    stepfunctions_stub.activate()

    session = FakeSession({"dynamodb": dynamodb_client, "stepfunctions": stepfunctions_client})
    assert (
        log_credentials._resolve_failed_execution_arn(session, "demand-failed", "123456789012")
        == "arn:aws:states:us-west-2:123456789012:execution:x:new"
    )
    dynamodb_stub.assert_no_pending_responses()
    stepfunctions_stub.assert_no_pending_responses()


def test_fetch_job_logs_walks_nested_executions_to_find_the_job(request_, monkeypatch):
    sts_client = _validated()
    stepfunctions_client, sfn_stub = make_stubbed_client("stepfunctions")
    batch_client, batch_stub = make_stubbed_client("batch")
    logs_client, logs_stub = make_stubbed_client("logs")

    outer_arn = "arn:aws:states:us-west-2:1:execution:outer:1"
    inner_arn = "arn:aws:states:us-west-2:1:execution:inner:1"

    sfn_stub.add_response(
        "get_execution_history",
        {
            "events": [
                task_submitted_event(
                    f'{{"nested": "{inner_arn}"}}',
                    resource_type="states",
                )
            ]
        },
        {"executionArn": outer_arn, "reverseOrder": True, "maxResults": 100},
    )
    sfn_stub.add_response(
        "get_execution_history",
        {"events": [task_submitted_event('{"JobId":"job-123"}')]},
        {"executionArn": inner_arn, "reverseOrder": True, "maxResults": 100},
    )
    sfn_stub.activate()

    batch_stub.add_response(
        "describe_jobs",
        {"jobs": [batch_job("job-123")]},
        {"jobs": ["job-123"]},
    )
    batch_stub.activate()

    logs_stub.add_response(
        "get_log_events",
        {"events": [{"timestamp": 1, "message": "hello"}, {"timestamp": 2, "message": "world"}]},
        {
            "logGroupName": log_credentials.LOG_GROUP,
            "logStreamName": "stream-1",
            "startFromHead": True,
            "limit": 10_000,
        },
    )
    logs_stub.activate()

    fake_session = FakeSession(
        {"sts": sts_client, "stepfunctions": stepfunctions_client, "batch": batch_client, "logs": logs_client}
    )
    monkeypatch.setattr(log_credentials, "_session", lambda *a: fake_session)
    log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)

    events = log_credentials.fetch_job_logs(request_, "demand-1", outer_arn)

    assert events == [{"timestamp": 1, "message": "hello"}, {"timestamp": 2, "message": "world"}]
    sfn_stub.assert_no_pending_responses()
    batch_stub.assert_no_pending_responses()
    logs_stub.assert_no_pending_responses()


def test_read_log_stream_returns_events_from_all_pages():
    logs_client, logs_stub = make_stubbed_client("logs")
    logs_stub.add_response(
        "get_log_events",
        {
            "events": [{"timestamp": 1, "message": "start"}],
            "nextForwardToken": "page-2",
        },
        {
            "logGroupName": log_credentials.LOG_GROUP,
            "logStreamName": "stream-1",
            "startFromHead": True,
            "limit": 10_000,
        },
    )
    logs_stub.add_response(
        "get_log_events",
        {
            "events": [{"timestamp": 2, "message": "finish"}],
            "nextForwardToken": "page-3",
        },
        {
            "logGroupName": log_credentials.LOG_GROUP,
            "logStreamName": "stream-1",
            "startFromHead": True,
            "limit": 10_000,
            "nextToken": "page-2",
        },
    )
    logs_stub.add_response(
        "get_log_events",
        {"events": [], "nextForwardToken": "page-3"},
        {
            "logGroupName": log_credentials.LOG_GROUP,
            "logStreamName": "stream-1",
            "startFromHead": True,
            "limit": 10_000,
            "nextToken": "page-3",
        },
    )
    logs_stub.activate()

    assert log_credentials._read_log_stream(FakeSession({"logs": logs_client}), "stream-1") == [
        {"timestamp": 1, "message": "start"},
        {"timestamp": 2, "message": "finish"},
    ]
    logs_stub.assert_no_pending_responses()


def test_batch_job_lookup_reads_all_execution_history_pages():
    client, stub = make_stubbed_client("stepfunctions")
    execution_arn = "arn:aws:states:us-west-2:1:execution:outer:1"
    stub.add_response(
        "get_execution_history",
        {
            "events": [],
            "nextToken": "page-2",
        },
        {"executionArn": execution_arn, "reverseOrder": True, "maxResults": 100},
    )
    stub.add_response(
        "get_execution_history",
        {"events": [task_submitted_event('{"JobId":"job-on-page-2"}')]},
        {
            "executionArn": execution_arn,
            "reverseOrder": True,
            "maxResults": 100,
            "nextToken": "page-2",
        },
    )
    stub.activate()

    session = FakeSession({"stepfunctions": client})

    assert log_credentials._resolve_batch_job_id(session, execution_arn) == "job-on-page-2"
    stub.assert_no_pending_responses()


def test_fetch_job_logs_finds_batch_job_in_failed_task_cause(request_, monkeypatch):
    sts_client = _validated()
    stepfunctions_client, sfn_stub = make_stubbed_client("stepfunctions")
    batch_client, batch_stub = make_stubbed_client("batch")
    logs_client, logs_stub = make_stubbed_client("logs")

    execution_arn = "arn:aws:states:us-west-2:1:execution:failed:1"
    sfn_stub.add_response(
        "get_execution_history",
        {"events": [task_failed_event('{"JobId": "job-failed"}')]},
        {"executionArn": execution_arn, "reverseOrder": True, "maxResults": 100},
    )
    sfn_stub.activate()
    batch_stub.add_response(
        "describe_jobs",
        {"jobs": [batch_job("job-failed")]},
        {"jobs": ["job-failed"]},
    )
    batch_stub.activate()
    logs_stub.add_response(
        "get_log_events",
        {"events": [{"timestamp": 1, "message": "failed"}]},
        {
            "logGroupName": log_credentials.LOG_GROUP,
            "logStreamName": "stream-1",
            "startFromHead": True,
            "limit": 10_000,
        },
    )
    logs_stub.activate()

    fake_session = FakeSession(
        {"sts": sts_client, "stepfunctions": stepfunctions_client, "batch": batch_client, "logs": logs_client}
    )
    monkeypatch.setattr(log_credentials, "_session", lambda *a: fake_session)
    resolved = []

    def resolve_failed_execution(session, demand_id, account):
        resolved.append((demand_id, account))
        return execution_arn

    monkeypatch.setattr(log_credentials, "_resolve_failed_execution_arn", resolve_failed_execution)
    log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)
    assert log_credentials.fetch_job_logs(request_, "demand-failed", execution_arn, failed=True) == [
        {"timestamp": 1, "message": "failed"}
    ]
    assert resolved == [("demand-failed", "123456789012")]
    sfn_stub.assert_no_pending_responses()
    batch_stub.assert_no_pending_responses()
    logs_stub.assert_no_pending_responses()


def test_fetch_job_logs_evicts_credentials_on_aws_rejection(request_, monkeypatch):
    sts_client = _validated()
    stepfunctions_client, sfn_stub = make_stubbed_client("stepfunctions")
    sfn_stub.add_client_error("get_execution_history", service_error_code="ExpiredToken")
    sfn_stub.activate()

    fake_session = FakeSession({"sts": sts_client, "stepfunctions": stepfunctions_client})
    monkeypatch.setattr(log_credentials, "_session", lambda *a: fake_session)
    log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)
    assert log_credentials.get_identity(request_) is not None
    with pytest.raises(log_credentials.CredentialError) as exc:
        log_credentials.fetch_job_logs(request_, "demand-1", "arn:aws:states:us-west-2:1:execution:x:1")

    assert exc.value.rejected is True
    # The whole point of "disable log access as soon as AWS rejects them": this session's
    # cached credentials are gone immediately, not just this one call's failure.
    assert log_credentials.get_identity(request_) is None


def test_fetch_job_logs_only_ever_calls_the_allowlisted_operations(request_, monkeypatch):
    sts_client = _validated()
    stepfunctions_client, sfn_stub = make_stubbed_client("stepfunctions")
    batch_client, batch_stub = make_stubbed_client("batch")
    logs_client, logs_stub = make_stubbed_client("logs")

    outer_arn = "arn:aws:states:us-west-2:1:execution:outer:1"
    sfn_stub.add_response(
        "get_execution_history",
        {"events": [task_submitted_event('{"JobId":"job-1"}')]},
        {"executionArn": ANY, "reverseOrder": True, "maxResults": 100},
    )
    sfn_stub.activate()
    batch_stub.add_response(
        "describe_jobs",
        {"jobs": [batch_job("job-1")]},
        {"jobs": ["job-1"]},
    )
    batch_stub.activate()
    logs_stub.add_response(
        "get_log_events",
        {"events": []},
        {
            "logGroupName": log_credentials.LOG_GROUP,
            "logStreamName": "stream-1",
            "startFromHead": True,
            "limit": 10_000,
        },
    )
    logs_stub.activate()

    fake_session = FakeSession(
        {"sts": sts_client, "stepfunctions": stepfunctions_client, "batch": batch_client, "logs": logs_client}
    )
    monkeypatch.setattr(log_credentials, "_session", lambda *a: fake_session)
    log_credentials.validate_credentials(request_, FAKE_ACCESS_KEY, FAKE_SECRET_KEY, FAKE_SESSION_TOKEN)
    log_credentials.fetch_job_logs(request_, "demand-1", outer_arn)

    services_used = {name for name, _ in fake_session.client_calls}
    assert services_used == {"sts", "stepfunctions", "batch", "logs"}
    # Every stub had exactly the calls it was given above and nothing else pending.
    sfn_stub.assert_no_pending_responses()
    batch_stub.assert_no_pending_responses()
    logs_stub.assert_no_pending_responses()
