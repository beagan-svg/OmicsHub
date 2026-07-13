import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static as static_url
import json

register = template.Library()


@register.simple_tag
def asset(path):
    """Like {% static %}, but appends the file's mtime as ?v= so browsers
    re-fetch an asset whenever it actually changes (no manual versioning,
    no stale-cache surprises). Falls back to the plain URL if not found."""
    url = static_url(path)
    abs_path = finders.find(path)
    if abs_path and os.path.exists(abs_path):
        return f"{url}?v={int(os.path.getmtime(abs_path))}"
    return url

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, '')


@register.filter
def status_label(value):
    """Display label for a processing status: 'Not Started' reads as 'Not Completed'.
    Display-only — the stored status value is unchanged."""
    return 'Not Completed' if value == 'Not Started' else value

@register.filter(name='split')
def split(value, delimiter=','):
    """
    Split a string into a list.
    
    Usage:
       {{ value|split:',' }}
    """
    return value.split(delimiter)

@register.filter(name='is_selected')
def is_selected(value, options_list):
    """
    Check if a value is in the provided list and return 'selected' if true.
    
    Usage:
       {{ value|is_selected:list }}
    
    Example:
       {{ "option1"|is_selected:selected_options }}
       Returns 'selected' if "option1" is in selected_options, otherwise ''
    """
    if not options_list:
        return ''
    
    return 'selected' if value in options_list else ''

@register.simple_tag
def pagination_info(page_obj):
    """
    Generate pagination info text.
    
    Usage:
       {% pagination_info page_obj %}
    """
    return f"Results {page_obj.start_index()}-{page_obj.end_index()} of {page_obj.paginator.count}"

@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    """
    Return encoded URL parameters that are the same as the current
    request's parameters, only with the specified GET parameters added or changed.

    It also removes any empty parameters to keep things neat,
    so you can remove a parameter by setting it to an empty string.
    """
    d = context['request'].GET.copy()
    for k, v in kwargs.items():
        d[k] = v
    # Remove any empty parameters
    for k in list(d.keys()):
        if not d[k]:
            del d[k]
    return d.urlencode()

@register.filter(name='jsonify')
def jsonify(obj):
    """Convert a Python object to JSON string for use in JavaScript"""
    return json.dumps(obj) 