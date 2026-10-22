"""
The activity log: one Event for each thing a user does that matters for
understanding how the app is used (activity/events.py records them). The
rest of the database only keeps how things are now, e.g. a withdrawn request
or a cancelled ride is deleted, and User.last_login only keeps the last one;
events keep what happened and when, for the admin's user statistics
(accounts/stats.py) and Metabase (the analytics.events view).

Events hold no personal details: no names, addresses, places searched for,
messages, IP addresses or browser details. data only has counts, choices and
yes/no values (see each kind below). Events of a deleted account are kept
without the user, and after ACTIVITY_ANONYMISE_DAYS every event is kept
without its user and ride (events.anonymise_old_events), so that the
statistics keep their history without it being anyone's.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Kind(models.TextChoices):
    # Visits: the first request of each day (activity/middleware.py).
    # data: device (mobile, desktop)
    ACTIVE = "active", _("Used the app")

    # Accounts
    SIGNED_UP = "signed_up", _("Signed up")
    EMAIL_CONFIRMED = "email_confirmed", _("Confirmed the email address")
    LOGGED_IN = "logged_in", _("Logged in")
    LOGGED_OUT = "logged_out", _("Logged out")
    WELCOMED = "welcomed", _("Saw the welcome popup")
    # data: fields (the names of the fields changed)
    PROFILE_SAVED = "profile_saved", _("Changed the profile")
    # data: changed ({field: new value}, all of them choices or yes/no)
    SETTINGS_SAVED = "settings_saved", _("Changed the settings")
    PHOTO_ADDED = "photo_added", _("Added a photo")
    PHOTO_REMOVED = "photo_removed", _("Removed the photo")
    EMAIL_CHANGE_REQUESTED = "email_change_requested", _("Asked to change the email address")
    EMAIL_CHANGED = "email_changed", _("Changed the email address")
    # Recorded without the user. data: domain, days (as a member), rides,
    # requests (made, ever)
    ACCOUNT_DELETED = "account_deleted", _("Deleted the account")

    # Searching. data: results, on_the_way (results passing by on the
    # way), start, destination, date (whether each was searched for),
    # start_campus, destination_campus (the campus searched for, if one
    # was), transport (the ways of travelling ticked)
    SEARCHED = "searched", _("Searched for rides")
    # data: role (driver, passenger, requested, other)
    RIDE_VIEWED = "ride_viewed", _("Opened a ride")

    # Drivers. RIDE_POSTED data: transport, one_time, one_way, seats, vias,
    # price, note (whether there is one), days_ahead (one-time rides),
    # days_a_week (recurring rides), destination_campus, groups (how many
    # groups it was posted to, 0 for everyone)
    RIDE_POSTED = "ride_posted", _("Posted a ride")
    # data: places (whether the start, stops or destination changed)
    RIDE_EDITED = "ride_edited", _("Changed a ride")
    # data: passengers, pending (requests), upcoming (whether it had not
    # left yet), hours_old
    RIDE_DELETED = "ride_deleted", _("Deleted a ride")
    # REQUEST_* by the driver. data: hours (since the request was made)
    REQUEST_ACCEPTED = "request_accepted", _("Accepted a request")
    REQUEST_DECLINED = "request_declined", _("Declined a request")
    PASSENGER_REMOVED = "passenger_removed", _("Removed a passenger")

    # Passengers. REQUEST_SENT data: message (whether there is one), seats_left
    REQUEST_SENT = "request_sent", _("Asked to join a ride")
    # data: hours (since the request was made)
    REQUEST_WITHDRAWN = "request_withdrawn", _("Withdrew a request")
    PASSENGER_LEFT = "passenger_left", _("Left a ride")

    # Groups (groups/services.py)
    GROUP_CREATED = "group_created", _("Made a group")
    GROUP_JOINED = "group_joined", _("Joined a group")
    GROUP_LEFT = "group_left", _("Left a group")

    # Notifications. NOTIFICATION_OPENED data: kind, minutes (after it was sent)
    NOTIFICATION_OPENED = "notification_opened", _("Opened a notification")
    NOTIFICATIONS_READ = "notifications_read", _("Marked notifications read")
    PUSH_ON = "push_on", _("Turned push notifications on")
    PUSH_OFF = "push_off", _("Turned push notifications off")


class Event(models.Model):
    # Kept, without the user, when the account is deleted
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="events")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    # Not a foreign key, so that events about a ride are kept when it is deleted
    ride_id = models.UUIDField(null=True, blank=True)
    # Details of the kind, see Kind
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["kind", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} ({self.user or _('deleted user')})"
