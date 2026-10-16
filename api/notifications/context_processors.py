from django.conf import settings

from . import push


def notifications(request):
    """
    unread_notification_count, shown on the bell, in the side menu and on
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
    """STATIC_VERSION, for the ?v= of the app's script URLs (see settings)."""
    return {"STATIC_VERSION": settings.STATIC_VERSION}
