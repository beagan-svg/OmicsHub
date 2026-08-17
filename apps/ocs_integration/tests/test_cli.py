"""The one CLI call: submitting a demand."""

from __future__ import annotations

import json
import subprocess

import pytest
from django.test import override_settings

from apps.ocs_integration import cli
from apps.ocs_integration.cli import OCSSubmissionError, OCSSubmissionUncertain

SUBMITTED = json.dumps({"demand_status": "SUBMITTED", "demand_execution": {"demand_id": "abc-123"}})


@pytest.fixture
def fake_run(monkeypatch):
    calls = []

    def _run(stdout=SUBMITTED, stderr="", returncode=0, side_effect=None):
        def run(argv, **kwargs):
            calls.append({"argv": argv, **kwargs})
            if side_effect:
                raise side_effect
            return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)

        monkeypatch.setattr(cli.subprocess, "run", run)
        return calls

    return _run


def test_returns_the_demand_id(fake_run):
    fake_run()

    assert cli.submit(["ocs", "fastqs", "align", "tenx-arc"]) == "abc-123"


def test_region_preflight_failure_is_safe_to_retry(fake_run):
    fake_run(
        stdout="",
        stderr="Could not determine region from default session or environment",
        returncode=1,
    )

    with pytest.raises(OCSSubmissionError):
        cli.submit(["ocs", "fastqs", "align", "tenx-arc"])


@override_settings(OCS_CLI_PATH="/opt/gcs/bin/ocs")
def test_runs_the_configured_executable(fake_run):
    """The config file says "ocs"; the backend runs the path it was given, not PATH."""
    calls = fake_run()

    cli.submit(["ocs", "fastqs", "align", "tenx-arc"])

    assert calls[0]["argv"] == ["/opt/gcs/bin/ocs", "fastqs", "align", "tenx-arc"]


class TestSubprocessEnvironment:
    """A worker is not a login shell, so the CLI's environment is supplied explicitly."""

    def test_pythonpath_is_not_inherited(self, fake_run, monkeypatch):
        monkeypatch.setenv("PYTHONPATH", "/already/here")
        calls = fake_run()

        cli.submit(["ocs", "fastqs", "align", "tenx-arc"])

        assert "PYTHONPATH" not in calls[0]["env"]

    @override_settings(AWS_PROFILE="omicshub")
    def test_the_cli_gets_the_same_aws_profile_as_the_reads(self, fake_run):
        """Otherwise submissions authenticate differently from the status checks."""
        calls = fake_run()

        cli.submit(["ocs", "fastqs", "align", "tenx-arc"])

        assert calls[0]["env"]["AWS_PROFILE"] == "omicshub"

    @override_settings(OCS_AWS_REGION="us-west-2")
    def test_the_cli_gets_the_configured_aws_region(self, fake_run):
        calls = fake_run()

        cli.submit(["ocs", "fastqs", "align", "tenx-arc"])

        assert calls[0]["env"]["AWS_REGION"] == "us-west-2"
        assert calls[0]["env"]["AWS_DEFAULT_REGION"] == "us-west-2"

    @override_settings(AWS_PROFILE="")
    def test_unset_values_leave_the_environment_alone(self, fake_run, monkeypatch):
        monkeypatch.delenv("PYTHONPATH", raising=False)
        monkeypatch.delenv("AWS_PROFILE", raising=False)
        calls = fake_run()

        cli.submit(["ocs", "fastqs", "align", "tenx-arc"])

        assert "PYTHONPATH" not in calls[0]["env"]
        assert "AWS_PROFILE" not in calls[0]["env"]


class TestTheCommandItself:
    """The first element is the config's `ocs` literal and is dropped for the real path."""

    def test_a_command_that_does_not_start_with_ocs_is_refused(self, fake_run):
        """Otherwise dropping element zero shifts every argument by one."""
        calls = fake_run()

        with pytest.raises(OCSSubmissionError, match="must start with 'ocs'"):
            cli.submit(["fastqs", "align", "tenx-arc"])

        assert calls == []

    def test_an_empty_command_is_refused(self, fake_run):
        calls = fake_run()

        with pytest.raises(OCSSubmissionError):
            cli.submit([])

        assert calls == []

    def test_a_missing_executable_is_a_plain_failure(self, fake_run):
        """A misconfigured OCS_CLI_PATH means nothing ran, so nothing reached OCS."""
        fake_run(side_effect=FileNotFoundError(2, "No such file or directory"))

        with pytest.raises(OCSSubmissionError, match="No `ocs` executable"):
            cli.submit(["ocs", "fastqs", "align", "tenx-arc"])


class TestOutcomeIsKnownOrNot:
    """Whether a retry is safe turns entirely on which of these two the caller sees."""

    def test_a_refusal_is_a_plain_failure(self, fake_run):
        """OCS answered and said no, so nothing is running and a retry is safe."""
        fake_run(stdout=json.dumps({"demand_status": "REJECTED"}))

        with pytest.raises(OCSSubmissionError):
            cli.submit(["ocs", "fastqs", "align", "tenx-arc"])

    def test_a_non_zero_exit_is_uncertain(self, fake_run):
        """The CLI can fail after submitting, so only a parsed refusal is a safe retry."""
        fake_run(stdout="", stderr="AccessDenied: not your queue\n", returncode=2)

        with pytest.raises(OCSSubmissionUncertain, match="AccessDenied: not your queue"):
            cli.submit(["ocs", "fastqs", "align", "tenx-arc"])

    def test_a_non_zero_exit_falls_back_to_stdout(self, fake_run):
        """Some failures are only ever printed to stdout; the reason must survive either way."""
        fake_run(stdout="no such asset tag\n", stderr="", returncode=1)

        with pytest.raises(OCSSubmissionUncertain, match="no such asset tag"):
            cli.submit(["ocs", "fastqs", "align", "tenx-arc"])

    def test_a_timeout_is_uncertain(self, fake_run):
        """The command may have submitted before it stopped answering."""
        fake_run(side_effect=subprocess.TimeoutExpired("ocs", 300))

        with pytest.raises(OCSSubmissionUncertain):
            cli.submit(["ocs", "fastqs", "align", "tenx-arc"])

    def test_unreadable_output_is_uncertain(self, fake_run):
        """A demand may exist; we simply cannot read the answer."""
        fake_run(stdout="Warning: profile expired\n")

        with pytest.raises(OCSSubmissionUncertain):
            cli.submit(["ocs", "fastqs", "align", "tenx-arc"])

    def test_a_response_without_a_status_is_uncertain(self, fake_run):
        fake_run(stdout=json.dumps({"demand_execution": {"demand_id": "abc-123"}}))

        with pytest.raises(OCSSubmissionUncertain):
            cli.submit(["ocs", "fastqs", "align", "tenx-arc"])
