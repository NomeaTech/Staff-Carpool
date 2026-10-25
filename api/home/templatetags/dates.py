from datetime import time

from django import template
from django.utils import dateformat, formats, translation

register = template.Library()


@register.filter(expects_localtime=True)
def localized(value, name):
    """
    {{ value|localized:"SHORT_WEEKDAY_DATE_FORMAT" }}: a date, datetime or
    time in one of the app's own formats, in the current language
    (carpool/formats/). "" for no value.
    """
    if value in (None, ""):
        return ""
    if isinstance(value, time):
        return dateformat.time_format(value, format_named(name))
    return dateformat.format(value, format_named(name))


def format_named(name):
    """The current language's format called name, from carpool/formats/."""
    for module in formats.get_format_modules(translation.get_language()):
        if hasattr(module, name):
            return getattr(module, name)
    # The language has no formats of its own
    for module in formats.get_format_modules("en"):
        if hasattr(module, name):
            return getattr(module, name)
    raise ValueError(f"No date format named {name}")
