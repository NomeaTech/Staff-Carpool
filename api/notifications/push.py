"""
PWA push notifications (Web Push), for Chrome, Edge, Firefox and Safari,
including the app installed on a phone's home screen.

- A user turns them on for a device on the profile page
  (static/js/push.js). The browser's subscription is saved as a
  PushSubscription (views.push_subscribe).
- push_channel (one of the delivery channels in services.CHANNELS) sends
  each notification to all of the recipient's subscriptions.
- The service worker (static/js/serviceworker.js) shows it, and opens its
  page when it is tapped.

The push services only accept notifications signed with the server's VAPID
key pair (settings.VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY, made with
"python manage.py generate_vapid_keys"). Without the keys, push
notifications are turned off.
"""
import json
import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.templatetags.static import static
from django.utils import timezone
from pywebpush import WebPushException, webpush

logger = logging.getLogger(__name__)

# How long a push service keeps trying to deliver a notification to a device
# that is offline, in seconds
TIME_TO_LIVE = 24 * 60 * 60
TIMEOUT = 10

# The browsers' push services. The server sends notifications to the
# endpoint a browser gives, so only these are accepted: any other address
# would have the server send requests wherever a user chose, e.g. to
# services on its own network.
PUSH_SERVICE_HOSTS = (
    "fcm.googleapis.com",           # Chrome, Edge on Android, Opera, Samsung Internet...
    "android.googleapis.com",       # Older Chrome subscriptions
    "updates.push.services.mozilla.com",  # Firefox
    ".push.apple.com",              # Safari (web.push.apple.com)
    ".notify.windows.com",          # Edge on Windows
)
ENDPOINT_MAX_LENGTH = 2000


def allowed_endpoint(endpoint):
    """Whether endpoint is an HTTPS address of one of the PUSH_SERVICE_HOSTS."""
    if not isinstance(endpoint, str) or len(endpoint) > ENDPOINT_MAX_LENGTH:
        return False
    try:
        url = urlsplit(endpoint)
        port = url.port
    except ValueError:
        return False
    host = (url.hostname or "").lower()
    return (url.scheme == "https" and port in (None, 443) and not url.username and not url.password
            and any(host == allowed or (allowed.startswith(".") and host.endswith(allowed))
                    for allowed in PUSH_SERVICE_HOSTS))


def enabled():
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def payload(request, notification):
    """What the service worker shows: the notification, with its icon."""
    return {
        **notification.as_payload(),
        "icon": static("images/icons/android-chrome-192x192.png"),
        "badge": static("images/icons/favicon-32x32.png"),
    }


def push_channel(request, notification):
    """Sends the notification to each device the recipient turned push on for."""
    if not enabled():
        return
    data = json.dumps(payload(request, notification))
    for subscription in notification.recipient.push_subscriptions.all():
        send(subscription, data)


def send(subscription, data):
    # Subscriptions saved before the endpoints were checked
    if not allowed_endpoint(subscription.endpoint):
        subscription.delete()
        return False
    try:
        webpush(
            subscription_info=subscription.as_subscription_info(),
            data=data,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            ttl=TIME_TO_LIVE,
            timeout=TIMEOUT,
        )
    except WebPushException as error:
        status = getattr(error.response, "status_code", None)
        # The device has unsubscribed, or the app was uninstalled
        if status in (404, 410):
            subscription.delete()
        else:
            logger.warning("Push notification failed (%s): %s", status, error)
        return False
    except Exception:
        logger.exception("Could not send a push notification")
        return False
    subscription.last_used_at = timezone.now()
    subscription.save(update_fields=["last_used_at"])
    return True
