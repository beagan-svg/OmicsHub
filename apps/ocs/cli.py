"""Send alignment and post-alignment commands through the `ocs` CLI.

Read metadata, stage status, and in-flight job counts from DynamoDB.
in `dynamodb.py`. Submission stays on the CLI because it is a write path with real
argument handling and validation behind it that this backend should not reimplement.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess

from django.conf import settings

logger = logging.getLogger(__name__)


class OCSSubmissionError(Exception):
    """Report that OCS refused the command and a retry is safe."""


class OCSSubmissionUncertain(Exception):
    """Report that the command may have reached OCS, so retrying could duplicate the job.

    A timeout, a non-zero exit or unparseable output all mean the CLI got far enough to
    have submitted; only an explicit refusal from OCS proves it did not.
    """


def _subprocess_env() -> dict[str, str]:
    """Store the environment for the `ocs` command.

    A worker process is not a login shell, so it inherits none of the shell setup that
    makes `ocs` work interactively. Two things have to be supplied:

* PYTHONPATH: the CLI's own venv resolves its packages through this, which is what
      the `activateocs` shell function exports. Without it the command dies on
      ModuleNotFoundError before it reaches OCS.
* AWS_PROFILE: the CLI resolves credentials itself, so it needs the same profile the
      DynamoDB reads use. Otherwise submissions authenticate differently from the status
      checks, or not at all.
    """
    env = os.environ.copy()

    if settings.OCS_CLI_PYTHONPATH:
        inherited = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            f"{settings.OCS_CLI_PYTHONPATH}:{inherited}" if inherited else settings.OCS_CLI_PYTHONPATH
        )

    if settings.AWS_PROFILE:
        env["AWS_PROFILE"] = settings.AWS_PROFILE

    return env


def submit(command_args: list[str]) -> str:
    """Send an `ocs` command and return the created demand id.

    The command's first element is the `ocs` executable name from the config file; it is
    replaced with the configured path so the backend does not depend on PATH. It is
checked rather than assumed. Commands reach here partly from a user-edited submit
    modal, and dropping the first element of something that was not `ocs` would shift
    every argument by one.
    """
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
        # Nothing ran, so nothing reached OCS: a misconfigured path, safe to retry once fixed.
        raise OCSSubmissionError(f"No `ocs` executable at {settings.OCS_CLI_PATH!r}") from error

    if result.returncode != 0:
        # A non-zero exit is not an explicit refusal from OCS — the CLI may have failed
        # after submitting — so the outcome is unknown rather than safely retryable.
        raise OCSSubmissionUncertain(
            f"`ocs` exited {result.returncode}: {(result.stderr or result.stdout).strip()}"
        )

    try:
        payload = json.loads(result.stdout)
        submitted = payload["demand_status"] == "SUBMITTED"
    except (json.JSONDecodeError, KeyError) as error:
        raise OCSSubmissionUncertain(f"Unreadable response from `ocs`: {result.stdout}") from error

    if not submitted:
        raise OCSSubmissionError(f"OCS did not accept the submission: {result.stdout}")

    return payload["demand_execution"]["demand_id"]
