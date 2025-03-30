from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, '')

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