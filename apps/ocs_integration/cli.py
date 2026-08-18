"""Send alignment and post-alignment commands through the `ocs` CLI."""

from __future__ import annotations

import json
import logging
import os
import subprocess

from django.conf import settings

logger = logging.getLogger(__name__)


class OCSSubmissionError(Exception):
    """Report that the command did not return a successful OCS submission."""


def _subprocess_env() -> dict[str, str]:
    """Return the environment required by the `ocs` command."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    if settings.AWS_PROFILE:
        env["AWS_PROFILE"] = settings.AWS_PROFILE
    if settings.OCS_AWS_REGION:
        env["AWS_REGION"] = settings.OCS_AWS_REGION
        env["AWS_DEFAULT_REGION"] = settings.OCS_AWS_REGION

    return env


def submit(command_args: list[str]) -> str:
    """Run an `ocs` command and return its demand id."""
    if not command_args or command_args[0] != "ocs":
        raise OCSSubmissionError(
            f"Command must start with 'ocs', not {command_args[0]!r}" if command_args else "Command is empty"
        )

    argv = [settings.OCS_CLI_PATH, *command_args[1:]]
    logger.info("Submitting to OCS: %s", " ".join(argv))

    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=settings.OCS_CLI_TIMEOUT,
            env=_subprocess_env(),
        )
    except subprocess.TimeoutExpired as error:
        raise OCSSubmissionError(f"`ocs` did not return within {settings.OCS_CLI_TIMEOUT}s") from error
    except FileNotFoundError as error:
        # The process did not start, so the command did not reach OCS.
        raise OCSSubmissionError(f"No `ocs` executable at {settings.OCS_CLI_PATH!r}") from error

    if result.returncode != 0:
        error_message = f"`ocs` exited {result.returncode}: {(result.stderr or result.stdout).strip()}"
        raise OCSSubmissionError(error_message)

    try:
        payload = json.loads(result.stdout)
        submitted = payload["demand_status"] == "SUBMITTED"
    except (json.JSONDecodeError, KeyError) as error:
        raise OCSSubmissionError(f"Unreadable response from `ocs`: {result.stdout}") from error

    if not submitted:
        raise OCSSubmissionError(f"OCS did not accept the submission: {result.stdout}")

    return payload["demand_execution"]["demand_id"]
