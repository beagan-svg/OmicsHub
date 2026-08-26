"""View a demand's AWS Batch container logs using credentials the viewer supplies.

This is deliberately separate from dynamodb.py and s3.py. The execution ARN comes from
the local StageStatus mirror. The temporary session built here is used only for the
Step Functions, Batch, and CloudWatch Logs calls needed to read one job's logs.

The AWS operations below are the entire allowlist: sts:GetCallerIdentity,
dynamodb:GetItem, states:ListExecutions, states:GetExecutionHistory (the Step Functions
IAM action prefix; the boto3 client is named "stepfunctions"), batch:DescribeJobs, and
logs:GetLogEvents. No other boto3 client is ever constructed from a viewer-supplied
credential, and the session backing that client is never installed as boto3's default,
never written to os.environ, and never persists past the request that builds it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.cache import cache

LOG_GROUP = "/aws/batch/job"

_CACHE_KEY_PREFIX = "sts_creds:v1:"

_EXECUTION_ARN_RE = re.compile(r"arn:aws:states:[^\"']*execution:[^\"'\s]*")

# AWS error codes that mean these particular credentials are no good -- expired, revoked,
# malformed -- rather than some other transient problem. Any of these evicts the cached
# credentials immediately, per "disable log access as soon as ... AWS rejects them."
_REJECTION_CODES = {
    "ExpiredToken",
    "ExpiredTokenException",
    "InvalidClientTokenId",
    "UnrecognizedClientException",
    "AccessDenied",
    "AccessDeniedException",
    "SignatureDoesNotMatch",
}

# What the viewer is told for each AWS error code. Never the raw exception: botocore's
# str(error) includes the full request, which can carry account ids and resource ARNs
# that have no reason to reach a browser.
_REDACTED_MESSAGES = {
    "ExpiredToken": "These credentials have expired.",
    "ExpiredTokenException": "These credentials have expired.",
    "InvalidClientTokenId": "AWS rejected these credentials.",
    "UnrecognizedClientException": "AWS rejected these credentials.",
    "SignatureDoesNotMatch": "AWS rejected these credentials.",
    "AccessDenied": "These credentials do not have permission for this action.",
    "AccessDeniedException": "These credentials do not have permission for this action.",
}
_DEFAULT_MESSAGE = "AWS rejected this request."
_UNREACHABLE_MESSAGE = "Could not reach AWS."


class CredentialError(Exception):
    """An already-redacted, user-facing error. Safe to show in a response as-is."""

    def __init__(self, code: str, message: str, *, rejected: bool = False):
        super().__init__(message)
        self.code = code
        self.rejected = rejected


class NoCredentials(Exception):
    """No (or no longer valid) cached credentials for this session."""


@dataclass(frozen=True)
class ValidatedIdentity:
    account: str
    arn: str


def _cache_key(session_key: str) -> str:
    return f"{_CACHE_KEY_PREFIX}{session_key}"


def _fernet() -> Fernet:
    key = settings.CREDENTIAL_ENCRYPTION_KEY
    return Fernet(key.encode() if isinstance(key, str) else key)


def _call(operation, /, *args, **kwargs):
    """Call one AWS operation, reducing any failure to a redacted CredentialError."""
    try:
        return operation(*args, **kwargs)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        raise CredentialError(
            code, _REDACTED_MESSAGES.get(code, _DEFAULT_MESSAGE), rejected=code in _REJECTION_CODES
        ) from None
    except BotoCoreError:
        raise CredentialError("Unreachable", _UNREACHABLE_MESSAGE) from None


def _session(access_key: str, secret_key: str, session_token: str) -> boto3.Session:
    """Build a boto3 session from exactly these three values -- nothing else.

    Never boto3.setup_default_session(), never os.environ, never profile_name. This
    object is used and dropped within a single request; it is not what gets cached (the
    three strings are, encrypted, so a fresh session is built from them each time).
    """
    return boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
    )


def validate_credentials(request, access_key: str, secret_key: str, session_token: str) -> ValidatedIdentity:
    """Validate credentials via STS and cache them for this session if they check out.

    Raises CredentialError (already redacted) if AWS rejects them. Never falls back to
    any other identity -- a validation failure here means the feature does not work for
    this session, not that some other AWS identity is tried instead.
    """
    if not (access_key and secret_key and session_token):
        raise CredentialError("MissingValue", "All three credential values are required.")

    session = _session(access_key, secret_key, session_token)
    identity = _call(session.client("sts").get_caller_identity)
    validated = ValidatedIdentity(account=identity["Account"], arn=identity["Arn"])

    payload = {
        "access_key": access_key,
        "secret_key": secret_key,
        "session_token": session_token,
        "account": validated.account,
        "arn": validated.arn,
    }
    encrypted = _fernet().encrypt(json.dumps(payload).encode())
    cache.set(
        _cache_key(request.session.session_key), encrypted, timeout=settings.LOG_VIEWER_CREDENTIAL_TTL_SECONDS
    )
    return validated


def clear_credentials(request) -> None:
    cache.delete(_cache_key(request.session.session_key))


def get_identity(request) -> ValidatedIdentity | None:
    """Return the cached identity for this session, or None if there isn't one."""
    creds = _get_cached(request)
    if creds is None:
        return None
    return ValidatedIdentity(account=creds["account"], arn=creds["arn"])


def _get_cached(request) -> dict[str, str] | None:
    encrypted = cache.get(_cache_key(request.session.session_key))
    if encrypted is None:
        return None
    try:
        decrypted = _fernet().decrypt(encrypted)
    except InvalidToken:
        # The encryption key rotated out from under an old cache entry. Treat it the same
        # as "gone" rather than raising -- it is exactly as unusable either way.
        cache.delete(_cache_key(request.session.session_key))
        return None
    return json.loads(decrypted.decode())


def fetch_job_logs(
    request,
    demand_id: str,
    execution_arn: str | None,
    *,
    failed: bool = False,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return the first log events for one demand's Batch job.

    Raises NoCredentials if this session has no cached (or no longer valid) credentials,
    or CredentialError (already redacted) if AWS rejects the request. Callers must check
    the demand id is one this viewer is allowed to see (currently running, recently
    finished, or failed) before calling this -- this function does not repeat that check.
    """
    creds = _get_cached(request)
    if creds is None:
        raise NoCredentials

    session = _session(creds["access_key"], creds["secret_key"], creds["session_token"])

    try:
        if failed:
            execution_arn = _resolve_failed_execution_arn(session, demand_id, creds["account"])
        elif not execution_arn:
            raise CredentialError("MissingExecutionArn", "This demand has no stored execution record yet.")
        job_id = _resolve_batch_job_id(session, execution_arn)
        if job_id is None:
            raise CredentialError("NotFound", "This demand has no Batch container log.")
        log_stream = _resolve_log_stream(session, job_id)
        if log_stream is None:
            raise CredentialError("NotFound", "This job has no log stream yet.")
        return _tail_log_stream(session, log_stream, limit=limit)
    except CredentialError as exc:
        if exc.rejected:
            clear_credentials(request)
        raise


def _resolve_failed_execution_arn(session: boto3.Session, demand_id: str, account: str) -> str:
    """Find the Step Functions execution created for a failed demand."""
    workflow_name = _resolve_demand_workflow(session, demand_id)
    if not workflow_name:
        raise CredentialError("NotFound", "Could not locate this failed demand in the OCS demand registry.")

    state_machine_arn = (
        f"arn:aws:states:{settings.OCS_AWS_REGION}:{account}:stateMachine:"
        f"{settings.OCS_ENV_BASE}-{workflow_name}"
    )
    stepfunctions = session.client("stepfunctions", region_name=settings.OCS_AWS_REGION)
    request = {"stateMachineArn": state_machine_arn, "maxResults": 1000}
    newest_match = None
    while True:
        response = _call(stepfunctions.list_executions, **request)
        for execution in response.get("executions", []):
            if execution.get("name", "").startswith(demand_id) and (
                newest_match is None or execution.get("startDate", 0) > newest_match.get("startDate", 0)
            ):
                newest_match = execution
        next_token = response.get("nextToken")
        if not next_token:
            break
        request["nextToken"] = next_token

    if newest_match is None:
        raise CredentialError(
            "NotFound", "Could not locate a Step Functions execution for this failed demand."
        )
    return newest_match["executionArn"]


def _resolve_demand_workflow(session: boto3.Session, demand_id: str) -> str | None:
    """Read the workflow name for a demand from the temporary session's registry."""
    dynamodb = session.client("dynamodb", region_name=settings.OCS_AWS_REGION)
    response = _call(
        dynamodb.get_item,
        TableName=f"{settings.OCS_ENV_BASE}-demand-registry",
        Key={"demand_id": {"S": demand_id}},
        ProjectionExpression="#request",
        ExpressionAttributeNames={"#request": "request"},
    )
    request = response.get("Item", {}).get("request", {}).get("M", {})
    return request.get("demand_workflow_name", {}).get("S")


def _resolve_batch_job_id(session: boto3.Session, execution_arn: str) -> str | None:
    """Walk a demand's Step Functions execution to the Batch job it submitted.

    A demand's own execution starts smaller nested executions before the one that
    actually submits the container job; a job id can appear in a successful TaskSubmitted
    output or a failed TaskFailed cause, so both are checked before following a nested
    execution one level deeper. This follows the same execution-history approach as
    ocs-execution-scripts/show_demand_log_stream.sh.
    """
    if not execution_arn:
        return None

    stepfunctions = session.client("stepfunctions", region_name=settings.OCS_AWS_REGION)
    current_arn = execution_arn
    visited_arns = set()
    while current_arn not in visited_arns:
        visited_arns.add(current_arn)
        nested_arn = None
        request = {"executionArn": current_arn, "reverseOrder": True, "maxResults": 100}
        while True:
            response = _call(stepfunctions.get_execution_history, **request)
            events = response["events"]
            for event in events:
                details = event.get("taskSubmittedEventDetails", {})
                if event.get("type") == "TaskSubmitted" and details.get("resourceType") == "batch":
                    job_id = _extract_job_id(details.get("output"))
                    if job_id:
                        return job_id
                if event.get("type") == "TaskFailed":
                    details = event.get("taskFailedEventDetails", {})
                    if details.get("resourceType") == "batch":
                        job_id = _extract_job_id(details.get("cause"))
                        if job_id:
                            return job_id
                if event.get("type") == "TaskSubmitted" and details.get("resourceType") == "states":
                    nested_arn = nested_arn or _extract_execution_arn(details.get("output"))

            # The token belongs to this page, so request the next page before following
            # a nested execution. reverseOrder keeps the first matching Batch event newest.
            next_token = response.get("nextToken")
            if not next_token:
                break
            request["nextToken"] = next_token
        if not nested_arn:
            return None
        current_arn = nested_arn
    return None


def _extract_job_id(output: str) -> str | None:
    if not isinstance(output, str):
        return None
    match = re.search(r'"JobId"\s*:\s*"([^"]+)"', output)
    return match.group(1) if match else None


def _extract_execution_arn(output: str) -> str | None:
    match = _EXECUTION_ARN_RE.search(output)
    return match.group(0) if match else None


def _resolve_log_stream(session: boto3.Session, job_id: str) -> str | None:
    batch = session.client("batch", region_name=settings.OCS_AWS_REGION)
    jobs = _call(batch.describe_jobs, jobs=[job_id])["jobs"]
    if not jobs:
        return None
    container_log_stream = jobs[0].get("container", {}).get("logStreamName")
    if container_log_stream:
        return container_log_stream
    attempts = jobs[0].get("attempts", [])
    return next(
        (
            attempt.get("container", {}).get("logStreamName")
            for attempt in reversed(attempts)
            if attempt.get("container", {}).get("logStreamName")
        ),
        None,
    )


def _tail_log_stream(session: boto3.Session, log_stream: str, *, limit: int) -> list[dict[str, Any]]:
    logs_client = session.client("logs", region_name=settings.OCS_AWS_REGION)
    events: list[dict[str, Any]] = []
    next_token = None
    while len(events) < limit:
        request = {
            "logGroupName": LOG_GROUP,
            "logStreamName": log_stream,
            "startFromHead": True,
            "limit": limit - len(events),
        }
        if next_token:
            request["nextToken"] = next_token
        response = _call(logs_client.get_log_events, **request)
        events.extend(response["events"])
        new_token = response.get("nextForwardToken")
        if not response["events"] or new_token == next_token:
            break
        next_token = new_token
    return [{"timestamp": event["timestamp"], "message": event["message"]} for event in events]
