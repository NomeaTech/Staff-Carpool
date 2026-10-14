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


# Notifications about changes to a trip the user is part of. Users who
# only want essential emails (User.email_notifications) get emails for these.
ESSENTIAL = {
    Kind.PASSENGER_LEFT,
    Kind.REQUEST_ACCEPTED,
    Kind.REQUEST_DECLINED,
    Kind.PASSENGER_REMOVED,
    Kind.RIDE_UPDATED,
    Kind.RIDE_CANCELLED,
}

# What each kind says. %(name)s is the other person, %(route)s the ride.
MESSAGES = {
    Kind.REQUEST_RECEIVED: _("%(name)s would like to join your ride %(route)s."),
    Kind.REQUEST_WITHDRAWN: _("%(name)s withdrew their request to join your ride %(route)s."),
    Kind.PASSENGER_LEFT: _("%(name)s left your ride %(route)s. Their seat is free again."),
    Kind.REQUEST_ACCEPTED: _("%(name)s accepted your request to join %(route)s."),
    Kind.REQUEST_DECLINED: _("%(name)s declined your request to join %(route)s."),
    Kind.PASSENGER_REMOVED: _("%(name)s removed you from the ride %(route)s."),
    Kind.RIDE_UPDATED: _("%(name)s changed the ride %(route)s. Check the new details."),
    Kind.RIDE_CANCELLED: _("%(name)s cancelled the ride %(route)s."),
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
}


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    # Kept when the ride is deleted (e.g. "ride cancelled"); data has its route
    ride = models.ForeignKey("test_app.Ride", on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
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
        return str(MESSAGES[Kind(self.kind)]) % {"name": self.data.get("name", ""), "route": self.data.get("route", "")}

    def url(self):
        """Where opening it leads: its ride, if the ride still exists."""
        if self.kind == Kind.RIDE_CANCELLED or not self.ride_id:
            return None
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
