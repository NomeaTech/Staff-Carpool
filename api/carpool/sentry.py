"""
Error reporting and bug reports with Sentry (https://sentry.io).

- Errors in the server (views, emails, management commands) and in the
  browser are sent to Sentry, with the release (STATIC_VERSION) they
  happened in and the ID of the user they happened to.
- Members can send a bug report from the More page ("Report a bug", Sentry's
  feedback form, static/js/support.js). It comes with a recording of
  the moments before it (session replay), with all text and images hidden.

Ad blockers (uBlock Origin, Brave) block requests to Sentry and scripts
named after it. So the browser's script has a name of its own
(static/js/vendor/kyyti-support-*.js), and it sends everything to the app
(tunnel), which passes it on to Sentry. Where the script is blocked anyway,
"Report a bug" opens the app's own form (home/views.py report_bug), which the
server sends (send_feedback).

Nothing else about the user is sent: no name, email, IP address, cookies or
form contents. Without SENTRY_DSN (e.g. in development) it is all off; the
server's side is started in settings.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import sentry_sdk
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

# How long passing an envelope on to Sentry may take
FORWARD_TIMEOUT = 10


def _same_dsn(dsn, other):
    """Whether two DSNs are the same project's key, whatever their spelling."""
    a, b = urlparse(dsn or ""), urlparse(other or "")
    return bool(a.hostname) and (a.username, a.hostname, a.path.strip("/")) == (b.username, b.hostname, b.path.strip("/"))


def forward(envelope):
    """
    Passes an envelope (Sentry's format for events, replays and feedback) on
    to the project of SENTRY_DSN. Returns Sentry's status code, or 502 when
    Sentry could not be reached.
    """
    dsn = urlparse(settings.SENTRY_DSN)
    url = f"https://{dsn.hostname}/api/{dsn.path.strip('/')}/envelope/"
    try:
        response = requests.post(url, data=envelope, timeout=FORWARD_TIMEOUT,
                                 headers={"Content-Type": "application/x-sentry-envelope"})
    except requests.RequestException:
        logger.warning("Could not pass an envelope on to Sentry", exc_info=True)
        return 502
    return response.status_code


@csrf_exempt
@require_POST
def tunnel(request):
    """
    Where the browser sends errors, replays and bug reports (the tunnel option
    in static/js/support.js), to pass them on to Sentry. Only for our own
    project: an envelope for another DSN is refused, so that this cannot be
    used to send anything elsewhere. Anyone can send to our project with its
    public DSN anyway, so it needs no login. Envelopes larger than Django's
    DATA_UPLOAD_MAX_MEMORY_SIZE (2.5 MB) are refused by Django itself.
    """
    if not settings.SENTRY_DSN:
        return HttpResponseNotFound()
    envelope = request.body
    try:
        header = json.loads(envelope.split(b"\n", 1)[0])
    except ValueError:
        return HttpResponseBadRequest()
    if not isinstance(header, dict) or not _same_dsn(header.get("dsn"), settings.SENTRY_DSN):
        return HttpResponseBadRequest()
    return HttpResponse(status=forward(envelope))


def send_feedback(message, user, url, user_agent):
    """
    Sends a bug report from the app's own form (home/views.py report_bug) to
    Sentry, as Sentry's feedback form would: the same user ID, release and
    environment, and the browser (from its User-Agent). Returns whether
    Sentry took it.
    """
    event_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    feedback = {
        "event_id": event_id,
        "timestamp": now.timestamp(),
        "platform": "python",
        "type": "feedback",
        "level": "info",
        "release": settings.SENTRY_RELEASE,
        "environment": settings.SENTRY_ENVIRONMENT,
        "user": {"id": str(user.pk)},
        # Shows which form it came from, in Sentry's list of feedback
        "tags": {"form": "app"},
        "contexts": {"feedback": {"message": message, "url": url}},
        "request": {"url": url, "headers": {"User-Agent": user_agent}},
    }
    envelope = b"\n".join(json.dumps(part).encode() for part in (
        {"event_id": event_id, "sent_at": now.isoformat(), "dsn": settings.SENTRY_DSN},
        {"type": "feedback"},
        feedback,
    ))
    return forward(envelope) == 200


class UserMiddleware:
    """
    Adds the logged-in user's ID to the errors of the request, so that the
    team can find the account in the admin.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if settings.SENTRY_DSN and user is not None and user.is_authenticated:
            sentry_sdk.set_user({"id": str(user.pk)})
        return self.get_response(request)


def context(request):
    """
    sentry_config: the browser's settings for static/js/support.js (see
    templates/_sentry.html), with the feedback form's texts in the page's
    language. Not there without SENTRY_DSN.
    """
    if not settings.SENTRY_DSN:
        return {}
    user = getattr(request, "user", None)
    return {"sentry_config": {
        # The DSN is public: it only lets the browser send events
        "dsn": settings.SENTRY_DSN,
        # Everything is sent to Sentry through the app (tunnel)
        "tunnel": reverse("support_relay"),
        "environment": settings.SENTRY_ENVIRONMENT,
        "release": settings.SENTRY_RELEASE,
        "user_id": str(user.pk) if user is not None and user.is_authenticated else None,
        "feedback": {
            "formTitle": _("Report a bug"),
            "messageLabel": _("Description"),
            "messagePlaceholder": _("What went wrong? What did you expect to happen?"),
            "isRequiredLabel": _("(required)"),
            "submitButtonLabel": _("Send report"),
            "cancelButtonLabel": _("Cancel"),
            "confirmButtonLabel": _("Confirm"),
            "successMessageText": _("Thank you for your report!"),
            "addScreenshotButtonLabel": _("Add a screenshot"),
            "removeScreenshotButtonLabel": _("Remove screenshot"),
            "highlightToolText": _("Highlight"),
            "hideToolText": _("Hide"),
            "removeHighlightText": _("Remove"),
            "errorEmptyMessageText": _("Describe the problem before sending the report."),
            "errorGenericText": _("The report could not be sent. Check your connection and try again."),
            "errorTimeoutText": _("The report could not be sent. Check your connection and try again."),
        },
    }}
