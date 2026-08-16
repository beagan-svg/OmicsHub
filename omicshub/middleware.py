"""Add request ids to incoming requests and outgoing responses.

Chapter 7's guidance is that custom middleware is for what has to happen on every single
request, and to keep it cheap because it runs on every single request. A correlation id
qualifies on both counts: a `uuid4()` and two contextvar operations.
"""

from __future__ import annotations

from omicshub.logging_filters import (
    REQUEST_ID_HEADER,
    new_request_id,
    sanitize_request_id,
    set_request_id,
)


class RequestIDMiddleware:
    """Assign every request an id and return it in the response.

    Reusing an inbound `X-Request-ID` means the id a proxy or a browser already assigned
    is the one in our logs, so the trail is unbroken across hops. Echoing it in the
    response is what makes the id usable in a bug report: the person who hit the failure
    can read it off the response instead of us matching on timestamps.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = sanitize_request_id(request.headers.get(REQUEST_ID_HEADER)) or new_request_id()
        request.request_id = request_id
        # Deliberately not reset on the way out. Django logs `django.request` — the
        # "Internal Server Error: /path" line for every 5xx, which is the single line most
        # worth correlating — from `BaseHandler.get_response`, *after* the middleware chain
        # has returned. Resetting here stamps that line with "-" and breaks the trail at
        # precisely the failure it exists for. Nothing leaks between requests as a result:
        # this runs first, so the next request overwrites the value before anything reads
        # it, and each async request gets its own context anyway.
        set_request_id(request_id)
        response = self.get_response(request)
        response[REQUEST_ID_HEADER] = request_id
        return response
