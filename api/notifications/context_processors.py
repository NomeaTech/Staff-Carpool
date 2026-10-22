import os

from django.conf import settings

from . import push


def notifications(request):
    """
    unread_notification_count, shown on the bell, on the More page and on
    the dock. Counted once, and only when a template uses it.
    push_public_key: the VAPID public key, when push notifications are on
    (notifications/push.py).
    """
    if not request.user.is_authenticated:
        return {}
    counted = {}

    def unread_notification_count():
        if "count" not in counted:
            counted["count"] = request.user.notifications.filter(read_at__isnull=True).count()
        return counted["count"]

    return {
        "unread_notification_count": unread_notification_count,
        "push_public_key": push.enabled() and settings.VAPID_PUBLIC_KEY,
    }


def static_version(request):
    """
    STATIC_VERSION, for the ?v= of the app's script URLs (see settings), and
    TAILWIND_CSS_VERSION, for the stylesheet's: when it was last built.

    django-tailwind's own ?v= is the current time with DEBUG on, so each page
    linked a "new" stylesheet: Turbo then waited to load it before showing
    the page (and kept adding it to <head>).
    """
    return {"STATIC_VERSION": settings.STATIC_VERSION, "TAILWIND_CSS_VERSION": tailwind_css_version()}


_tailwind_css_file = None

def tailwind_css_version():
    global _tailwind_css_file
    if _tailwind_css_file is None:
        from django.contrib.staticfiles import finders
        from tailwind import get_config
        _tailwind_css_file = finders.find(get_config("TAILWIND_CSS_PATH")) or ""
    try:
        return int(os.path.getmtime(_tailwind_css_file))
    except OSError:
        return settings.STATIC_VERSION
