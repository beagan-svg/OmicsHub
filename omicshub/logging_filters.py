"""Attach request ids and redact email addresses in logs."""

from __future__ import annotations

import logging
import re
import traceback
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from celery import signals

if TYPE_CHECKING:
    from sentry_sdk.types import Event, Hint

# The inbound and outbound HTTP header, and the Celery message header the same value rides
# on when a request enqueues a task.
REQUEST_ID_HEADER = "X-Request-ID"
CELERY_HEADER = "request_id"

# What the formatter prints when there is no request in scope, such as a management command or
# module imported at startup. A literal placeholder keeps every log line the same shape.
NO_REQUEST_ID = "-"

# An inbound id is client input that lands in every log line for the request, so it is
# accepted only in the shape ids actually come in. Anything else (a newline, a megabyte of
# text) is discarded and a fresh id generated, rather than injected into the log stream.
VALID_REQUEST_ID = re.compile(r"\A[A-Za-z0-9._-]{1,64}\Z")

_request_id: ContextVar[str] = ContextVar("request_id", default="")


def new_request_id() -> str:
    return uuid4().hex


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str | None):
    """Set the id for the current context and return the token needed to unset it."""
    return _request_id.set(value or "")


def reset_request_id(token) -> None:
    _request_id.reset(token)


def sanitize_request_id(value: str | None) -> str:
    """Return the inbound request id when valid, or an empty value for a new id."""
    if value and VALID_REQUEST_ID.match(value):
        return value
    return ""


# --- redaction ------------------------------------------------------------

# Deliberately loose on the local part: the point is to catch anything that looks like an
# address, not to validate one. Over-matching costs a redacted token in a log line;
# under-matching leaks an address.
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]*\w")
REDACTED = "<redacted-email>"


def redact_emails(text: str) -> str:
    return EMAIL.sub(REDACTED, text)


class RequestIDFilter(logging.Filter):
    """Attach the current request id to every log record.

    A filter rather than a formatter subclass so the attribute exists no matter which
    formatter a handler uses, and so a record that never saw a request still renders.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or NO_REQUEST_ID
        return True


class EmailRedactingFilter(logging.Filter):
    """Remove email addresses from the log message and traceback.

    It works on the *rendered* message rather than on `record.args`, because the addresses
    do not arrive as strings: they are inside the argv list joined into one `%s`, and
    inside the `CalledProcessError` that `logger.exception` renders into a traceback. The
    rendering is only forced for records that contain an `@` at all, so the ordinary case
    keeps its lazy `%s` formatting.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "@" in message:
            record.msg = redact_emails(message)
            record.args = ()
        if record.exc_info and not record.exc_text:
            # Render it here so the redaction below sees it; `logging.Formatter` reuses
            # `exc_text` when it is already set, so nothing is formatted twice.
            record.exc_text = "".join(traceback.format_exception(*record.exc_info))
        if record.exc_text and "@" in record.exc_text:
            record.exc_text = redact_emails(record.exc_text)
        return True


def scrub_event(event: Event, hint: Hint | None = None) -> Event:
    """Remove email addresses from every value in a Sentry event.

        `send_default_pii=False` stops the SDK attaching the user and the request body, but it
    says nothing about an address that is part of a message or a stack frame. That is
        exactly where this app's addresses are. Passed as Sentry's `before_send`.
    """
    return _scrub(event)


def _scrub(value: Any, depth: int = 0) -> Any:
    # A Sentry event is a few levels of dicts and lists; the bound stops a cyclic or
    # pathologically deep payload from turning a redaction into a hang.
    if depth > 12:
        return value
    if isinstance(value, str):
        return redact_emails(value) if "@" in value else value
    if isinstance(value, dict):
        return {key: _scrub(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item, depth + 1) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub(item, depth + 1) for item in value)
    return value


# --- carrying the id across the Celery boundary ---------------------------


@signals.before_task_publish.connect
def _attach_request_id(headers=None, **kwargs) -> None:
    """Copy the publishing request id into the Celery message.

    Use `setdefault` so a caller that has already chosen an id keeps it when a retry
    republishes the original message.
    """
    request_id = get_request_id()
    if headers is not None and request_id:
        headers.setdefault(CELERY_HEADER, request_id)


@signals.task_prerun.connect
def _adopt_request_id(task=None, task_id=None, **kwargs) -> None:
    """Use the queuing request id when logging a Celery task.

    Fall back to the task id for beat-triggered work. The sweeps and reconciler have no request
    id, so the task id correlates each run with its own log records.
    """
    published = getattr(getattr(task, "request", None), CELERY_HEADER, None)
    set_request_id(published or task_id)


@signals.task_postrun.connect
def _clear_request_id(**kwargs) -> None:
    """Clear the request id before a prefork worker handles another task."""
    set_request_id("")
