"""Format sample, stage, and queue values for templates.

Both exist because the alternative is an `{% if %}` ladder repeated on four pages.
"""

import os

from django import template
from django.contrib.staticfiles.finders import find
from django.templatetags.static import static
from django.utils import timezone

register = template.Library()

# Mirrors views.DEFAULT_SORT; imported lazily there would be a circular import.
DEFAULT_SORT_KEY = "batch_name_from_vendor"

# OCS reports thirteen status labels; the design system has six meanings. This is the map
# between them, and it is the only place the two vocabularies meet. A new OCS status lands
# on `unknown` rather than on an arbitrary colour.
#
#   queued   waiting on something, nothing is happening yet
#   running  work is in flight
#   done     the stage finished successfully
#   warn     needs a human's attention but nothing failed
#   fail     the stage failed or was stopped
#   unknown  no status reported
STATUS_STATES = {
    "COMPLETED": "done",
    "ARCHIVED": "done",
    "INGEST_COMPLETE": "done",
    "SUBMITTED": "running",
    "SUBMITTING": "running",
    "IN_PROGRESS": "running",
    "PENDING": "queued",
    "AWAITING_TRIGGER": "queued",
    "CANCELLED": "queued",
    "FAILED": "fail",
    "ABORTED": "fail",
    # A demand OCS left unfinished and stopped updating. Warning rather than fail: the job
    # did not fail, it stopped being reported on, and the stage is free to run again.
    "ABANDONED": "warn",
    "NOT COMPLETED": "unknown",
}

# Define tooltip and accessible descriptions for statuses whose names are not self-explanatory.
STATUS_NOTES = {
    "AWAITING_TRIGGER": "Waiting for OCS to start it. Nothing is running yet.",
    "INGEST_COMPLETE": "Ingest finished. This sample is now due for alignment.",
    "IN_PROGRESS": "OCS is running this stage now.",
    "SUBMITTING": "The worker is handing this command to OCS.",
    "SUBMITTED": "OCS accepted the command and has not reported progress yet.",
    "ABANDONED": "OCS stopped reporting on this demand. It did not fail, and the stage can be run again.",
    "ABORTED": "The stage was stopped before it finished.",
    "NOT COMPLETED": "OCS has no status for this stage yet.",
}


@register.filter
def status_state(status):
    """Return a design-system state for an OCS or queue status label."""
    return STATUS_STATES.get(status, "unknown")


@register.filter
def status_note(status):
    """Return a plain-language status gloss, or "" when none is needed."""
    return STATUS_NOTES.get(status, "")


# The placeholder names as they read in the config, and as they read to a person.
FIELD_LABELS = {
    "reference_name": "Reference",
    "chemistry": "Chemistry",
    "probe_set": "Probe set",
    "execution_vcpus": "Execution vCPUs",
    "load_name": "Load name",
    "input_name": "Input name",
}


@register.filter
def field_label(name):
    """Return a placeholder name formatted as a form label."""
    return FIELD_LABELS.get(name, name.replace("_", " ").capitalize())


@register.filter
def since_short(value):
    """Return a short freshness label, such as `just now`, `12m ago`, or `3d ago`.

    The full `timesince` output is too long for the toolbar, so ages of at least one hour
    omit minute precision.
    """
    if not value:
        return "never"

    seconds = (timezone.now() - value).total_seconds()
    if seconds < 60:
        return "just now"
    for cutoff, unit, suffix in ((3600, 60, "m"), (86400, 3600, "h"), (None, 86400, "d")):
        if cutoff is None or seconds < cutoff:
            return f"{int(seconds // unit)}{suffix} ago"


@register.filter
def column_value(sample, column):
    """Return one column's value for a fastq sample."""
    return column.value_for(sample)


@register.filter
def mapping_value(mapping, key):
    """Return one value from a template mapping."""
    return mapping.get(key, "")


@register.filter
def stage_status(sample, stage):
    """Return a fastq sample's stage status for template calls."""
    return sample.stage_status(stage)


@register.simple_tag(takes_context=True)
def active_class(context, url_name):
    """Return `active` when the current page matches this navigation item."""
    match = context["request"].resolver_match
    return "active" if match and match.url_name == url_name else ""


@register.simple_tag(takes_context=True)
def with_params(context, **kwargs):
    """Return this view's query string with `kwargs` applied and empty values removed.

    Paging, sorting and the family tabs all mean "the view I am looking at, with one thing
    changed", and every one of them used to hand-build its own href. The links that built
    their own dropped the search, the organism and the four stage filters on the way, so
    switching tab quietly widened the view.

    `page` is dropped unless it is being set, because re-sorting or re-filtering while on
    page 7 should show the top of the new list, not its seventh page.
    """
    page_param = kwargs.pop("page_param", None) or "page"
    page_size_param = kwargs.pop("page_size_param", None) or "page_size"
    if page_param != "page" and "page" in kwargs:
        kwargs[page_param] = kwargs.pop("page")
    if page_size_param != "page_size" and "page_size" in kwargs:
        kwargs[page_size_param] = kwargs.pop("page_size")

    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    if page_param not in kwargs:
        params.pop(page_param, None)
    return params.urlencode()


@register.simple_tag(takes_context=True)
def sort_query(context, key):
    """Query string that sorts by `key`, preserving every other filter.

        Clicking the active column flips the direction; clicking any other column starts it
    descending, because the columns people sort by here, batch, load, and name, are ones
        where the newest or highest is what you want first.
    """
    params = context["request"].GET
    current = params.get("sort") or DEFAULT_SORT_KEY
    descending = (params.get("dir") or "desc") == "desc"
    return with_params(context, sort=key, dir="asc" if key == current and descending else "desc")


@register.simple_tag
def static_v(path: str) -> str:
    """`{% static %}` with the file's modification time appended as a version.

        Django's development static server answers with `Last-Modified` and no `Cache-Control`.
        A response with no explicit directive is *heuristically* cacheable: the browser is free
    to invent a freshness lifetime, commonly a tenth of the file's age, and serve the old
        bytes without revalidating at all. So a stylesheet edited an hour after it was last
        written can sit in Chrome's cache for minutes, and the page looks unchanged while the
        server is serving the new file to anything with an empty cache.

        Appending the mtime makes the URL itself change whenever the file does, which no cache
        can defeat. In production `ManifestStaticFilesStorage` already hashes the name and this
        is redundant but harmless.
    """
    url = static(path)
    absolute = find(path)
    if not absolute:
        return url
    try:
        return f"{url}?v={int(os.path.getmtime(absolute))}"
    except OSError:
        return url
