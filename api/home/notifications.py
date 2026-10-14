"""
Emails about ride requests, sent to members who have not turned them off
(User.notify_ride_requests). The emails only link to the ride, they never
contain anyone's contact details.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _

from accounts.privacy import display_name

logger = logging.getLogger(__name__)


def absolute_url(request, path):
    return f"{settings.SITE_URL}{path}" if settings.SITE_URL else request.build_absolute_uri(path)


def notify(request, recipient, subject, template, **context):
    if not recipient.notify_ride_requests or not recipient.email:
        return

    ride = context["ride"]
    body = render_to_string(f"emails/{template}.txt", {
        **context,
        "recipient": recipient,
        "route": ride.route_name(),
        "url": absolute_url(request, reverse("ride_detail", args=[ride.pk])),
        "account_url": absolute_url(request, reverse("account")),
    })

    def send():
        try:
            send_mail(subject, body, None, [recipient.email])
        except Exception:
            logger.exception("Could not send the %s email", template)

    # Sent once the change is saved, and not at all if it is rolled back
    transaction.on_commit(send)


def request_received(request, ride_request):
    ride = ride_request.ride
    notify(
        request, ride.driver, _("New request to join your ride"), "request_received",
        ride=ride, passenger=display_name(ride_request.passenger), message=ride_request.message,
    )


def request_answered(request, ride_request):
    ride = ride_request.ride
    accepted = ride_request.status == ride_request.Status.ACCEPTED
    notify(
        request, ride_request.passenger,
        _("Your ride request was accepted") if accepted else _("Your ride request was declined"),
        "request_answered", ride=ride, accepted=accepted, driver=display_name(ride.driver, partner=accepted),
    )


def passenger_left(request, ride_request):
    ride = ride_request.ride
    notify(
        request, ride.driver, _("A passenger left your ride"), "passenger_left",
        ride=ride, passenger=display_name(ride_request.passenger, partner=True),
    )


def ride_cancelled(request, ride):
    """Sent to everyone who requested or joined the ride, before it is deleted."""
    for ride_request in ride.requests.exclude(status=ride.requests.model.Status.DECLINED).select_related("passenger"):
        notify(
            request, ride_request.passenger, _("A ride you requested was cancelled"), "ride_cancelled",
            ride=ride, driver=display_name(ride.driver),
        )


def ride_updated(request, ride):
    """Sent to everyone who requested or joined the ride when its driver edits it."""
    for ride_request in ride.requests.exclude(status=ride.requests.model.Status.DECLINED).select_related("passenger"):
        notify(
            request, ride_request.passenger, _("A ride you requested was changed"), "ride_updated",
            ride=ride, driver=display_name(ride.driver),
        )
