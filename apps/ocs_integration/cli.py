"""Send alignment and post-alignment commands through the `ocs` CLI."""

from __future__ import annotations

import json
import logging
import os
import subprocess

from django.conf import settings

logger = logging.getLogger(__name__)

REGION_CONFIGURATION_ERROR = "Could not determine region from default session or environment"


class OCSSubmissionError(Exception):
    """Report that OCS refused the command and a retry is safe."""


class OCSSubmissionUncertain(Exception):
    """Report that retrying the command could create a duplicate OCS job."""


def is_safe_to_retry(error_message: str) -> bool:
    """Return whether a stranded error proves the command never reached OCS."""
    return REGION_CONFIGURATION_ERROR in error_message


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
        raise OCSSubmissionUncertain(f"`ocs` did not return within {settings.OCS_CLI_TIMEOUT}s") from error
    except FileNotFoundError as error:
        # The process did not start, so the command did not reach OCS.
        raise OCSSubmissionError(f"No `ocs` executable at {settings.OCS_CLI_PATH!r}") from error

    if result.returncode != 0:
        error_message = f"`ocs` exited {result.returncode}: {(result.stderr or result.stdout).strip()}"
        # This is a local CLI preflight failure. It happens before the command can contact
        # OCS, so it is safe to retry and should not be stranded like an unknown outcome.
        if is_safe_to_retry(error_message):
            raise OCSSubmissionError(error_message)
        # Other non-zero exits may happen after OCS accepted the command.
        raise OCSSubmissionUncertain(error_message)

    try:
        payload = json.loads(result.stdout)
        submitted = payload["demand_status"] == "SUBMITTED"
    except (json.JSONDecodeError, KeyError) as error:
        raise OCSSubmissionUncertain(f"Unreadable response from `ocs`: {result.stdout}") from error

    if not submitted:
        raise OCSSubmissionError(f"OCS did not accept the submission: {result.stdout}")

    return payload["demand_execution"]["demand_id"]
