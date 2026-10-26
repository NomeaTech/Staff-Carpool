"""
Error reporting and bug reports with Sentry (https://sentry.io).

- Errors in the server (views, emails, management commands) and in the
  browser are sent to Sentry, with the release (STATIC_VERSION) they
  happened in and the ID of the user they happened to.
- Members can send a bug report from the More page ("Report a bug", Sentry's
  feedback form, static/js/sentry-setup.js). It comes with a recording of
  the moments before it (session replay), with all text and images hidden.

Nothing else about the user is sent: no name, email, IP address, cookies or
form contents. Without SENTRY_DSN (e.g. in development) it is all off; the
server's side is started in settings.
"""
import sentry_sdk
from django.conf import settings
from django.utils.translation import gettext as _


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
    sentry_config: the browser's settings for static/js/sentry-setup.js (see
    templates/_sentry.html), with the feedback form's texts in the page's
    language. Not there without SENTRY_DSN.
    """
    if not settings.SENTRY_DSN:
        return {}
    user = getattr(request, "user", None)
    return {"sentry_config": {
        # The DSN is public: it only lets the browser send events
        "dsn": settings.SENTRY_DSN,
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
