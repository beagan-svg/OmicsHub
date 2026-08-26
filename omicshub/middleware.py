"""Add a request ID to each request and response."""

from __future__ import annotations

from omicshub.logging_filters import (
    REQUEST_ID_HEADER,
    new_request_id,
    sanitize_request_id,
    set_request_id,
)


class RequestIDMiddleware:
    """Reuse a valid inbound request ID and include it in the response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = sanitize_request_id(request.headers.get(REQUEST_ID_HEADER)) or new_request_id()
        request.request_id = request_id
        # Deliberately not reset on the way out. Django logs `django.request`, and the
        # "Internal Server Error: /path" line for every 5xx, which is the single line most
        # request remains available from `BaseHandler.get_response` after the middleware chain
        # has returned. Resetting here stamps that line with "-" and breaks the trail at
        # precisely the failure it exists for. Nothing leaks between requests as a result:
        # this runs first, so the next request overwrites the value before anything reads
        # it, and each async request gets its own context anyway.
        set_request_id(request_id)
        response = self.get_response(request)
        response[REQUEST_ID_HEADER] = request_id
        return response
