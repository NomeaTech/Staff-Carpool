"""
The error pages (400, 403, 404, 500, and a form's expired CSRF token), in
the site's own look (templates/error.html) rather than Django's plain ones.
Shown only with DEBUG off; with it on, Django shows its debugging pages.

They are rendered with the request, unlike Django's own 400 and 500 pages,
so that base.html has what its context processors give it. They are never
cached, so that a proxy (Cloudflare) does not keep serving an error after
it is fixed.
"""
import logging
import re

from django.shortcuts import render
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.utils.translation import gettext_lazy as _
from django.views import defaults

logger = logging.getLogger(__name__)

# The heading, the explanation, and the icon (home/templates/_icon.html)
ERRORS = {
    400: (_("Bad request"), _("The page could not handle the request. Go back and try again."), "alert"),
    403: (_("No access"), _("You do not have permission to see this page."), "lock"),
    404: (_("Page not found"), _("The page does not exist or has moved. Check the address, or start again from the home page."), "road"),
    500: (_("Something went wrong"), _("There was an error on our side. Try again in a moment."), "alert"),
}


# Pages opened from links (shared rides, notifications, emails) that are not
# found: what it was that is gone, by the start of the address. Matching the
# address also covers mistyped links that are not even IDs (/app/ride/abc).
# The first that matches is used: (pattern, heading, explanation, icon,
# (URL name, label) of the button that leads on).
NOT_FOUND = [
    (r"^/app/ride/[^/]+/edit/?$", _("Ride not found"),
     _("This ride does not exist, or you are not its driver. Only drivers can edit their rides."), "car",
     ("my_rides", _("My rides"))),
    (r"^/app/ride/", _("Ride not found"),
     _("This ride does not exist. Its driver may have deleted it, or the link may be wrong."), "car",
     ("search", _("Find a ride"))),
    (r"^/app/requests/", _("Request not found"),
     _("This request to join a ride no longer exists. The passenger may have withdrawn it, or the ride was deleted."), "car",
     ("my_rides", _("My rides"))),
    (r"^/app/groups/.", _("Group not found"),
     _("This group does not exist. Its admin may have deleted it, or the link may be wrong."), "user",
     ("groups", _("Groups"))),
    (r"^/app/notifications/.", _("Notification not found"),
     _("This notification does not exist, or it is not yours."), "bell",
     ("notifications", _("Notifications"))),
]


def error_page(request, status, message=None, heading=None, icon=None, action=None):
    default_heading, default_message, default_icon = ERRORS[status]
    try:
        response = render(request, "error.html", {
            "status": status,
            "heading": heading or default_heading,
            "message": message or default_message,
            "icon": icon or default_icon,
            # (URL, label) of the button that leads on; the home page without one
            "action": (reverse(action[0]), action[1]) if action else None,
        }, status=status)
    except Exception:
        # The error page itself failed (e.g. the database is down): Django's plain one
        logger.exception("Could not show the %s error page", status)
        response = defaults.server_error(request)
    add_never_cache_headers(response)
    return response


def bad_request(request, exception):
    return error_page(request, 400)


def permission_denied(request, exception):
    return error_page(request, 403)


def page_not_found(request, exception):
    for pattern, heading, message, icon, action in NOT_FOUND:
        if re.match(pattern, request.path):
            return error_page(request, 404, message, heading, icon, action)
    return error_page(request, 404)


def server_error(request):
    return error_page(request, 500)


def csrf_failure(request, reason=""):
    """A form posted with a missing or expired security token (CSRF_FAILURE_VIEW)."""
    return error_page(request, 403, _("The form had expired. Go back, reload the page and try again."))
