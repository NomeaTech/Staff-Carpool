"""
Sending notifications.

Every notification goes through send(): it is saved (shown in the app's
notification menu and list, and as a pop-up while the app is open, see
static/js/notifications.js) and then handed to each delivery channel in
CHANNELS.

Channels
--------
A channel is a function channel(request, notification):
- email_channel sends it if the recipient wants emails of its kind
  (User.wants_email: all notifications, or only essential ones)
- push.push_channel sends it as a push notification to each device the
  recipient turned them on for (see notifications/push.py)

Channels run once the change that caused the notification is saved
(transaction.on_commit), and not at all if it is rolled back.

Emails never contain anyone's contact details; they link to the ride.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse

from accounts.privacy import display_name
from .models import Kind, Notification
from .push import push_channel

logger = logging.getLogger(__name__)


def absolute_url(request, path):
    # request is None for notifications sent outside a request, e.g. when a
    # staff admin's change gives a group a new admin (groups/signals.py)
    if settings.SITE_URL or request is None:
        return f"{settings.SITE_URL}{path}"
    return request.build_absolute_uri(path)


def email_channel(request, notification):
    recipient = notification.recipient
    if not recipient.email or not recipient.wants_email(notification.kind):
        return

    ride_url = notification.url()
    body = render_to_string(f"emails/{notification.kind}.txt", {
        **notification.data,
        "recipient": recipient,
        "url": absolute_url(request, ride_url) if ride_url else None,
        "account_url": absolute_url(request, reverse("account")),
        "essential": notification.is_essential,
    })
    try:
        send_mail(notification.title(), body, None, [recipient.email])
    except Exception:
        logger.exception("Could not send the %s email", notification.kind)


# Each is called as channel(request, notification), see the module's docstring
CHANNELS = [email_channel, push_channel]


def send(request, recipient, kind, ride=None, group=None, **data):
    """
    Notifies recipient. data holds the details shown: "name" (the other
    person, as the recipient may see them) and anything the email needs.
    The ride's route and the group's name are added, so they are kept if
    the ride or group is deleted.
    """
    if ride is not None:
        data.setdefault("route", ride.route_name())
    if group is not None:
        data.setdefault("group", group.name)
    notification = Notification.objects.create(recipient=recipient, kind=kind, ride=ride, group=group, data=data)

    def deliver():
        for channel in CHANNELS:
            try:
                channel(request, notification)
            except Exception:
                logger.exception("Could not deliver notification %s", notification.pk)

    transaction.on_commit(deliver)
    return notification


# The events. The names shown follow accounts/privacy.py: ride partners see
# each other's full names, everyone else the name the person chose to show.

def request_received(request, ride_request):
    ride = ride_request.ride
    send(request, ride.driver, Kind.REQUEST_RECEIVED, ride,
         name=display_name(ride_request.passenger), message=ride_request.message)


def request_withdrawn(request, ride_request):
    ride = ride_request.ride
    send(request, ride.driver, Kind.REQUEST_WITHDRAWN, ride, name=display_name(ride_request.passenger))


def passenger_left(request, ride_request):
    ride = ride_request.ride
    send(request, ride.driver, Kind.PASSENGER_LEFT, ride, name=display_name(ride_request.passenger, partner=True))


def request_accepted(request, ride_request):
    ride = ride_request.ride
    send(request, ride_request.passenger, Kind.REQUEST_ACCEPTED, ride, name=display_name(ride.driver, partner=True))


def request_declined(request, ride_request):
    ride = ride_request.ride
    send(request, ride_request.passenger, Kind.REQUEST_DECLINED, ride, name=display_name(ride.driver))


def passenger_removed(request, ride_request):
    ride = ride_request.ride
    send(request, ride_request.passenger, Kind.PASSENGER_REMOVED, ride, name=display_name(ride.driver, partner=True))


def ride_updated(request, ride):
    """To everyone who requested or joined the ride, when its driver edits it."""
    for ride_request in active_requests(ride):
        send(request, ride_request.passenger, Kind.RIDE_UPDATED, ride, name=driver_name(ride, ride_request))


def ride_cancelled(request, ride):
    """To everyone who requested or joined the ride, before it is deleted."""
    for ride_request in active_requests(ride):
        send(request, ride_request.passenger, Kind.RIDE_CANCELLED, ride, name=driver_name(ride, ride_request))


def active_requests(ride):
    return ride.requests.exclude(status=ride.requests.model.Status.DECLINED).select_related("passenger")


def driver_name(ride, ride_request):
    return display_name(ride.driver, partner=ride_request.status == ride_request.Status.ACCEPTED)


def ride_hidden(request, ride, group):
    """To the driver of a ride posted only to groups, when the last of them is taken off it."""
    send(request, ride.driver, Kind.RIDE_HIDDEN, ride, group=group)


# Groups (groups/services.py). Group members see each other's names as
# everyone else does; only ride partners see full names.

def group_join_requested(request, admin, membership):
    send(request, admin, Kind.GROUP_JOIN_REQUESTED, group=membership.group, name=display_name(membership.user))


def group_join_answered(request, admin, membership, accepted):
    kind = Kind.GROUP_JOIN_ACCEPTED if accepted else Kind.GROUP_JOIN_DECLINED
    # A declined request is deleted, so the notification does not link to it
    send(request, membership.user, kind, group=membership.group, name=display_name(admin))


def group_member_removed(request, admin, membership):
    send(request, membership.user, Kind.GROUP_REMOVED, group=membership.group, name=display_name(admin))


def group_admin_granted(request, admin, membership):
    send(request, membership.user, Kind.GROUP_ADMIN_GRANTED, group=membership.group, name=display_name(admin))


def group_admin_handed_over(request, membership):
    send(request, membership.user, Kind.GROUP_ADMIN_HANDED_OVER, group=membership.group)


# Sent just before the group is deleted; the notification keeps its name

def group_deleted(request, admin, recipient, group):
    send(request, recipient, Kind.GROUP_DELETED, group=group, name=display_name(admin))


def group_closed(request, recipient, group):
    send(request, recipient, Kind.GROUP_CLOSED, group=group)
