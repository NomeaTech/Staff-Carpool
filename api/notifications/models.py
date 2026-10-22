"""
In-app notifications. Each one is also delivered through the channels in
notifications/services.py (email now, PWA push later).
"""
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class Kind(models.TextChoices):
    # To drivers
    REQUEST_RECEIVED = "request_received", _("New ride request")
    REQUEST_WITHDRAWN = "request_withdrawn", _("Ride request withdrawn")
    PASSENGER_LEFT = "passenger_left", _("Passenger left")
    # To passengers
    REQUEST_ACCEPTED = "request_accepted", _("Request accepted")
    REQUEST_DECLINED = "request_declined", _("Request declined")
    PASSENGER_REMOVED = "passenger_removed", _("Removed from a ride")
    RIDE_UPDATED = "ride_updated", _("Ride changed")
    RIDE_CANCELLED = "ride_cancelled", _("Ride cancelled")
    # To drivers of rides posted only to groups that are all gone
    RIDE_HIDDEN = "ride_hidden", _("Ride no longer shown")
    # Groups (groups/services.py). To admins:
    GROUP_JOIN_REQUESTED = "group_join_requested", _("Request to join a group")
    # To members, and people asking to join:
    GROUP_JOIN_ACCEPTED = "group_join_accepted", _("Joined a group")
    GROUP_JOIN_DECLINED = "group_join_declined", _("Group request declined")
    GROUP_REMOVED = "group_removed", _("Removed from a group")
    GROUP_ADMIN_GRANTED = "group_admin_granted", _("You are now a group admin")
    # When a group has no admin who can act and the member becomes one
    GROUP_ADMIN_HANDED_OVER = "group_admin_handed_over", _("You are now a group admin")
    GROUP_DELETED = "group_deleted", _("Group deleted")
    # When its last member left
    GROUP_CLOSED = "group_closed", _("Group closed")


# Notifications about changes to a trip the user is part of. Users who
# only want essential emails (User.email_notifications) get emails for these.
ESSENTIAL = {
    Kind.PASSENGER_LEFT,
    Kind.REQUEST_ACCEPTED,
    Kind.REQUEST_DECLINED,
    Kind.PASSENGER_REMOVED,
    Kind.RIDE_UPDATED,
    Kind.RIDE_CANCELLED,
    Kind.RIDE_HIDDEN,
    Kind.GROUP_JOIN_ACCEPTED,
    Kind.GROUP_JOIN_DECLINED,
    Kind.GROUP_REMOVED,
    Kind.GROUP_ADMIN_GRANTED,
    Kind.GROUP_ADMIN_HANDED_OVER,
    Kind.GROUP_DELETED,
    Kind.GROUP_CLOSED,
}

# What each kind says. %(name)s is the other person, %(route)s the ride,
# %(group)s the group.
MESSAGES = {
    Kind.REQUEST_RECEIVED: _("%(name)s would like to join your ride %(route)s."),
    Kind.REQUEST_WITHDRAWN: _("%(name)s withdrew their request to join your ride %(route)s."),
    Kind.PASSENGER_LEFT: _("%(name)s left your ride %(route)s. Their seat is free again."),
    Kind.REQUEST_ACCEPTED: _("%(name)s accepted your request to join %(route)s."),
    Kind.REQUEST_DECLINED: _("%(name)s declined your request to join %(route)s."),
    Kind.PASSENGER_REMOVED: _("%(name)s removed you from the ride %(route)s."),
    Kind.RIDE_UPDATED: _("%(name)s changed the ride %(route)s. Check the new details."),
    Kind.RIDE_CANCELLED: _("%(name)s cancelled the ride %(route)s."),
    Kind.RIDE_HIDDEN: _("Your ride %(route)s was only shown to %(group)s, which you are no longer in, so nobody can find it now. Edit the ride to choose who sees it."),
    Kind.GROUP_JOIN_REQUESTED: _("%(name)s would like to join %(group)s."),
    Kind.GROUP_JOIN_ACCEPTED: _("%(name)s accepted you into %(group)s. You can now see the rides posted to it."),
    Kind.GROUP_JOIN_DECLINED: _("%(name)s declined your request to join %(group)s."),
    Kind.GROUP_REMOVED: _("%(name)s removed you from %(group)s."),
    Kind.GROUP_ADMIN_GRANTED: _("%(name)s made you an admin of %(group)s. You can now answer requests to join it."),
    Kind.GROUP_ADMIN_HANDED_OVER: _("You are now an admin of %(group)s, as it had no admin left who could answer requests to join. You have been a member the longest. You can hand the role over to someone else on the group's page."),
    Kind.GROUP_DELETED: _("%(name)s deleted the group %(group)s."),
    Kind.GROUP_CLOSED: _("The group %(group)s was closed, as its last member left. Your request to join it was cancelled."),
}


# Icon (home/templates/_icon.html) and colour (Tailwind classes, written out
# in full so that Tailwind finds them) for each kind
STYLES = {
    Kind.REQUEST_RECEIVED: ("user", "bg-secondary/15 text-secondary"),
    Kind.REQUEST_WITHDRAWN: ("user", "bg-base-300 text-base-content/70"),
    Kind.PASSENGER_LEFT: ("user", "bg-warning/25 text-warning-content"),
    Kind.REQUEST_ACCEPTED: ("check", "bg-success/25 text-success-content"),
    Kind.REQUEST_DECLINED: ("x", "bg-error/15 text-error"),
    Kind.PASSENGER_REMOVED: ("x", "bg-error/15 text-error"),
    Kind.RIDE_UPDATED: ("calendar", "bg-info/20 text-info-content"),
    Kind.RIDE_CANCELLED: ("x", "bg-error/15 text-error"),
    Kind.RIDE_HIDDEN: ("alert", "bg-warning/25 text-warning-content"),
    Kind.GROUP_JOIN_REQUESTED: ("user", "bg-secondary/15 text-secondary"),
    Kind.GROUP_JOIN_ACCEPTED: ("check", "bg-success/25 text-success-content"),
    Kind.GROUP_JOIN_DECLINED: ("x", "bg-error/15 text-error"),
    Kind.GROUP_REMOVED: ("x", "bg-error/15 text-error"),
    Kind.GROUP_ADMIN_GRANTED: ("shield", "bg-info/20 text-info-content"),
    Kind.GROUP_ADMIN_HANDED_OVER: ("shield", "bg-warning/25 text-warning-content"),
    Kind.GROUP_DELETED: ("x", "bg-base-300 text-base-content/70"),
    Kind.GROUP_CLOSED: ("x", "bg-base-300 text-base-content/70"),
}

# Kinds about a group, which lead to the group's page
GROUP_KINDS = {kind for kind in Kind if kind.startswith("group_")}


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    # Kept when the ride is deleted (e.g. "ride cancelled"); data has its route
    ride = models.ForeignKey("rides.Ride", on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    # Kept when the group is deleted; data has its name
    group = models.ForeignKey("groups.Group", on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    # The details shown, as they were when it was sent: name, route, message
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read_at"])]

    def __str__(self):
        return f"{self.get_kind_display()} → {self.recipient}"

    @property
    def is_read(self):
        return self.read_at is not None

    @property
    def is_essential(self):
        return self.kind in ESSENTIAL

    def icon(self):
        return STYLES[Kind(self.kind)][0]

    def icon_class(self):
        return STYLES[Kind(self.kind)][1]

    def title(self):
        return str(self.get_kind_display())

    def message(self):
        """The notification's text, in the current language."""
        # The lazy texts are translated when turned into a string
        return str(MESSAGES[Kind(self.kind)]) % {
            "name": self.data.get("name", ""), "route": self.data.get("route", ""), "group": self.data.get("group", ""),
        }

    def url(self):
        """Where opening it leads: its group or ride, if it still exists."""
        if self.kind in GROUP_KINDS:
            gone = self.kind in (Kind.GROUP_DELETED, Kind.GROUP_CLOSED)
            return reverse("group_detail", args=[self.group_id]) if self.group_id and not gone else None
        if self.kind == Kind.RIDE_CANCELLED or not self.ride_id:
            return None
        if self.kind == Kind.RIDE_HIDDEN:
            return reverse("edit_ride", args=[self.ride_id])
        return reverse("ride_detail", args=[self.ride_id])

    def as_payload(self):
        """The notification for the browser: the live pop-ups, and later PWA push."""
        return {
            "id": str(self.pk),
            "kind": self.kind,
            "title": self.title(),
            "message": self.message(),
            "url": reverse("open_notification", args=[self.pk]),
            "created_at": self.created_at.isoformat(),
            "read": self.is_read,
        }


class PushSubscription(models.Model):
    """
    A browser or installed app that receives the user's notifications as
    push notifications (notifications/push.py). Saved when the user turns
    them on, on each device separately.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    # The push service's address for this browser, and its encryption keys
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} ({self.user_agent[:40]})"

    def as_subscription_info(self):
        return {"endpoint": self.endpoint, "keys": {"p256dh": self.p256dh, "auth": self.auth}}
