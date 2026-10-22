"""
Groups of members, and rides posted only to them.

Anyone can make a group and becomes its admin. Others ask to join, and an
admin accepts or declines them. Admins can make members admins, step down
and hand the role over (groups/services.py has the rules). A ride is posted
either to everyone or to one or more of its driver's groups (Ride.groups,
Ride.groups_only), and then only their members see it (RideQuerySet.visible_to).

A group always needs an admin who can act on it. When the last one leaves,
deletes their account, or can no longer use it (blocked, email no longer
confirmed, or not seen for GROUP_ADMIN_AWAY_DAYS), the member who has been
in the group longest becomes admin (services.ensure_admin).
"""
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

NAME_MAX_LENGTH = 60
DESCRIPTION_MAX_LENGTH = 500


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=NAME_MAX_LENGTH)
    description = models.TextField(_("description"), blank=True, default="", max_length=DESCRIPTION_MAX_LENGTH)
    # Kept for the record; it gives no rights (the admins are in memberships)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [Lower("name")]
        constraints = [
            # Two groups with the same name could be mistaken for each other
            models.UniqueConstraint(Lower("name"), name="group_name_unique"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("group_detail", args=[self.pk])

    def members(self):
        return self.memberships.filter(status=Membership.Status.ACTIVE)


class MembershipQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=Membership.Status.ACTIVE)

    def pending(self):
        return self.filter(status=Membership.Status.PENDING)

    def admins(self):
        return self.active().filter(role=Membership.Role.ADMIN)

    def able_to_act(self):
        """
        Memberships of people who can use their account now: not blocked,
        email confirmed, and seen within GROUP_ADMIN_AWAY_DAYS. Only they
        count as admins who can answer requests (services.ensure_admin).

        Sessions last long, so being seen is having logged in or used the
        app (the activity log's daily visits) in that time.
        """
        from activity.models import Event, Kind
        away = timezone.now() - timedelta(days=settings.GROUP_ADMIN_AWAY_DAYS)
        visited = Event.objects.filter(user=OuterRef("user"), kind=Kind.ACTIVE, created_at__gte=away)
        return self.filter(user__is_active=True, user__email_confirmed_at__isnull=False).filter(
            Q(user__last_login__gte=away) | Exists(visited))


class Membership(models.Model):
    """A member of a group, or (PENDING) a request to join one."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Asked to join")
        ACTIVE = "active", _("Member")

    class Role(models.TextChoices):
        MEMBER = "member", _("Member")
        ADMIN = "admin", _("Admin")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    # Not "groups": User already has that, for Django's permission groups
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_memberships")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    requested_at = models.DateTimeField(auto_now_add=True)
    # When the request was accepted. The longest-standing member is the one
    # who becomes admin when a group has none left.
    joined_at = models.DateTimeField(null=True, blank=True)

    objects = MembershipQuerySet.as_manager()

    class Meta:
        ordering = ["joined_at", "requested_at"]
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="one_membership_per_group_and_user"),
        ]

    def __str__(self):
        return f"{self.user} in {self.group} ({self.get_status_display()}, {self.get_role_display()})"

    @property
    def is_admin(self):
        return self.status == self.Status.ACTIVE and self.role == self.Role.ADMIN
