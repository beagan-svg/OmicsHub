"""Return one response shape for API failures.

Without this a client sees DRF's field-error dict for a validation failure, a bare
`{"detail": ...}` for a 404, and something else again for a permission error. They all
become `{"error": {"message": {<field>: [<message>, ...]}}}` instead.

Unrecognized exceptions fall through to a 500 response so unexpected outages remain visible.
"""

from rest_framework.settings import api_settings
from rest_framework.views import exception_handler as drf_exception_handler

# Where an error that belongs to no particular field is filed. A `ValidationError` raised
# directly in view code comes back from DRF as a bare list, which this module files under
# NON_FIELD_KEY; a `ValidationError` raised inside a serializer's own `validate()` comes back
# from DRF already keyed under `api_settings.NON_FIELD_ERRORS_KEY` ("non_field_errors" by
# default). Without normalizing the second case to the same key, a client reading one key
# would silently miss the other, even though both mean the same thing: an error that isn't
# about one particular field.
NON_FIELD_KEY = "detail"


def _as_field_errors(data):
    """Return field names mapped to lists of error messages."""
    if isinstance(data, dict):
        return {
            (NON_FIELD_KEY if field == api_settings.NON_FIELD_ERRORS_KEY else field): (
                messages if isinstance(messages, list) else [messages]
            )
            for field, messages in data.items()
        }
    if isinstance(data, list):
        return {NON_FIELD_KEY: data}
    return {NON_FIELD_KEY: [data]}


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    response.data = {"error": {"message": _as_field_errors(response.data)}}
    return response
