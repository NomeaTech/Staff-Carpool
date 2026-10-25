"""
Recording the activity log (activity/models.py). The views call record()
when something is done; logins and logouts are recorded here, from Django's
signals, and the daily visits by activity/middleware.py.

Nothing is recorded for the test user or about the test rides (rides/admin.py),
so that they never show up in the statistics. Recording never stops what the
user is doing: an error is logged and the event is left out.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db import transaction
from django.db.models import Q
from django.dispatch import receiver
from django.utils import timezone

from home.campuses import CAMPUSES
from rides.admin import TEST_RIDE_KEY, TEST_USER_EMAIL
from rides.transport import TRANSPORT_OPTIONS
from .models import Event, Kind

logger = logging.getLogger(__name__)

# The campuses by their place id, for naming the campus a search or ride is for
CAMPUS_NAMES = {campus["place"]["id"]: campus["place"]["displayName"] for campus in CAMPUSES}


def is_test_user(user):
    return user is not None and (user.email or "").lower() == TEST_USER_EMAIL


def is_test_ride(ride):
    return bool((ride.start_json or {}).get(TEST_RIDE_KEY)) or is_test_user(ride.driver)


def record(kind, user, ride=None, /, **data):
    """Records that user (None for a deleted account) did kind, about ride if given. data
    is the event's details, so any name can be used in it, even kind."""
    if is_test_user(user) or (ride is not None and is_test_ride(ride)):
        return None
    try:
        # A savepoint, so that a failure does not break the view's transaction
        with transaction.atomic():
            return Event.objects.create(kind=kind, user=user, ride_id=ride.pk if ride else None, data=data)
    except Exception:
        logger.exception("Could not record the %s event", kind)
        return None


def anonymise_old_events():
    """
    Removes the user and the ride from events older than ACTIVITY_ANONYMISE_DAYS.
    The ride goes too, as a ride that still exists names its driver and
    passengers. Run once a day by activity/middleware.py.
    """
    cutoff = timezone.now() - timedelta(days=settings.ACTIVITY_ANONYMISE_DAYS)
    try:
        return (Event.objects.filter(created_at__lt=cutoff)
                .filter(Q(user__isnull=False) | Q(ride_id__isnull=False))
                .update(user=None, ride_id=None))
    except Exception:
        logger.exception("Could not anonymise old events")
        return 0


def campus(place):
    """The campus a place (a ride's or search's start_json / destination_json) is, or None."""
    return CAMPUS_NAMES.get((place or {}).get("id"))


def transport(values):
    """The ways of travelling (Ride fields) set in values, a ride or a form's cleaned data."""
    get = values.get if isinstance(values, dict) else lambda field: getattr(values, field)
    return [option.field for option in TRANSPORT_OPTIONS if get(option.field)]


def hours_since(moment):
    return round((timezone.now() - moment) / timedelta(hours=1), 1)


def ride_details(ride):
    """RIDE_POSTED's data: what kind of ride it is, not where it goes."""
    details = {
        "transport": transport(ride),
        "one_time": ride.one_time,
        "one_way": ride.one_way,
        "seats": ride.max_passengers,
        "vias": ride.via_points.count(),
        "price": bool(ride.price),
        "note": bool(ride.note),
        "flexible_time": ride.flexible_time,
        "destination_campus": campus(ride.destination_json),
        # How many groups it was posted to; 0 is everyone
        "groups": ride.groups.count() if ride.groups_only else 0,
    }
    leaving_at = ride.leaving_at()
    if leaving_at:
        details["days_ahead"] = (leaving_at.date() - timezone.localdate()).days
    if not ride.one_time:
        details["days_a_week"] = sum(ride.day_filter())
    return details


@receiver(user_logged_in)
def logged_in(sender, request, user, **kwargs):
    record(Kind.LOGGED_IN, user)


@receiver(user_logged_out)
def logged_out(sender, request, user, **kwargs):
    if user is not None:
        record(Kind.LOGGED_OUT, user)
