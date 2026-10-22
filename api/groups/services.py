"""
What can be done with groups, and the rules for it. The views only call
these, so the rules hold however a group is changed.

Admins
------
- The person who makes a group is its first admin.
- Admins accept or decline requests to join, make members admins, remove
  members who are not admins, and edit or delete the group. Admins cannot
  remove each other: an admin steps down themselves.
- An admin can step down only if another admin who can act remains
  (MembershipQuerySet.able_to_act); otherwise they hand the role over to a
  member in the same step (hand_over).

A group is never left without an admin who can act
--------------------------------------------------
ensure_admin() runs whenever a membership changes (groups/signals.py): a
member leaves or is removed, an account is deleted, a request to join is
made, an account is blocked or its email address stops being confirmed (e.g.
when someone leaves LUT/LAB and does not confirm the address again), when a
member opens the group's page, and on each member's first visit of the day. If no admin can act, the member who has been
in the group longest and can act becomes admin and is told why. A group
whose last member goes is deleted. If nobody in it can act, the group waits
for a staff admin (groups/admin.py shows these groups).

Admins who come back keep their role, next to the new admin.

Rides posted to groups
----------------------
Drivers can only post to groups they are members of. When they leave or are
removed, or the group is deleted, the group is taken off their rides. A ride
posted only to groups that are all gone is shown to nobody (Ride.groups_only
stays set), never to everyone; its driver is told to choose again.
"""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.privacy import display_name
from activity import events
from activity.models import Kind as EventKind
from notifications import services as notifications
from .models import Group, Membership


class GroupError(Exception):
    """Something the rules do not allow; its message is shown to the user."""


def lock(group):
    """The group, locked until the transaction ends, so that changes to its members happen one at a time."""
    return Group.objects.select_for_update().get(pk=group.pk)


def membership_of(user, group):
    return Membership.objects.filter(group=group, user=user).first()


def require_admin(user, group):
    membership = membership_of(user, group)
    if membership is None or not membership.is_admin:
        raise PermissionDenied
    return membership


def can_act(membership):
    return Membership.objects.filter(pk=membership.pk).able_to_act().exists()


# Making and joining groups

def create_group(user, name, description=""):
    with transaction.atomic():
        group = Group.objects.create(name=name, description=description, created_by=user)
        Membership.objects.create(group=group, user=user, status=Membership.Status.ACTIVE,
                                  role=Membership.Role.ADMIN, joined_at=timezone.now())
    events.record(EventKind.GROUP_CREATED, user)
    return group


def request_to_join(request, user, group):
    with transaction.atomic():
        lock(group)
        if membership_of(user, group):
            return None
        # Saving it runs ensure_admin (groups/signals.py), so a group whose
        # admins are all away gets one who can answer before they are told
        membership = Membership.objects.create(group=group, user=user)
        admins = group.memberships.admins()
        # Those who can act; if none can, the others, who may come back
        for admin in (admins.able_to_act() or admins).select_related("user"):
            notifications.group_join_requested(request, admin.user, membership)
    return membership


def cancel_request(user, group):
    Membership.objects.filter(group=group, user=user, status=Membership.Status.PENDING).delete()


def answer_request(request, admin, membership, accept):
    with transaction.atomic():
        group = lock(membership.group)
        require_admin(admin, group)
        membership = Membership.objects.get(pk=membership.pk)
        if membership.status != Membership.Status.PENDING:
            return
        if accept:
            membership.status = Membership.Status.ACTIVE
            membership.joined_at = timezone.now()
            membership.save(update_fields=["status", "joined_at"])
            notifications.group_join_answered(request, admin, membership, accepted=True)
            events.record(EventKind.GROUP_JOINED, membership.user)
        else:
            notifications.group_join_answered(request, admin, membership, accepted=False)
            membership.delete()


# Admins

def make_admin(request, admin, membership):
    with transaction.atomic():
        group = lock(membership.group)
        require_admin(admin, group)
        membership = Membership.objects.get(pk=membership.pk)
        if membership.status != Membership.Status.ACTIVE or membership.is_admin:
            return
        if not can_act(membership):
            raise GroupError(_("%(name)s cannot be made an admin, as they have not used their account lately.")
                             % {"name": display_name(membership.user)})
        membership.role = Membership.Role.ADMIN
        membership.save(update_fields=["role"])
        notifications.group_admin_granted(request, admin, membership)


def step_down(admin, group):
    with transaction.atomic():
        group = lock(group)
        own = require_admin(admin, group)
        others = group.memberships.admins().able_to_act().exclude(pk=own.pk)
        if not others.exists():
            raise GroupError(_("You are the only admin. Choose someone to hand the role over to."))
        own.role = Membership.Role.MEMBER
        own.save(update_fields=["role"])


def hand_over(request, admin, membership):
    """Makes membership's member admin and the admin a member, in one step."""
    with transaction.atomic():
        make_admin(request, admin, membership)
        step_down(admin, membership.group)


def remove_member(request, admin, membership):
    with transaction.atomic():
        group = lock(membership.group)
        require_admin(admin, group)
        membership = Membership.objects.select_related("user").get(pk=membership.pk)
        if membership.status != Membership.Status.ACTIVE:
            return
        if membership.is_admin:
            raise GroupError(_("Admins cannot remove other admins. An admin can step down themselves."))
        unpost_rides(request, membership.user, group)
        notifications.group_member_removed(request, admin, membership)
        membership.delete()


def leave(request, user, group, successor=None):
    """
    Leaves the group. An admin who is the only one who can act chooses a
    successor (a membership), or the longest-standing member becomes admin.
    The last member leaving deletes the group.
    """
    with transaction.atomic():
        group = lock(group)
        own = membership_of(user, group)
        if own is None or own.status != Membership.Status.ACTIVE:
            return
        if own.is_admin and successor is not None and successor.group_id == group.pk and successor.pk != own.pk:
            if not group.memberships.admins().able_to_act().exclude(pk=own.pk).exists():
                make_admin(request, user, successor)
        unpost_rides(request, user, group)
        # Deleting it runs ensure_admin (groups/signals.py)
        own.delete()
    events.record(EventKind.GROUP_LEFT, user)


def ensure_admin(group, request=None):
    """Makes sure the group has an admin who can act; see the module's docstring."""
    group = Group.objects.filter(pk=group.pk).first()
    if group is None:
        return
    members = group.memberships.active()
    if not members.exists():
        close(request, group)
        return
    if members.admins().able_to_act().exists():
        return
    successor = members.able_to_act().order_by("joined_at", "requested_at").select_related("user").first()
    if successor is None:
        # Nobody in the group can act: a staff admin can choose one (groups/admin.py)
        return
    successor.role = Membership.Role.ADMIN
    successor.save(update_fields=["role"])
    notifications.group_admin_handed_over(request, successor)


def without(user):
    """
    What happens to user's groups if user goes (deletes their account), for
    warning them first: (group, successor) for each group they are the only
    admin who can act in. successor is the membership that would become
    admin (as ensure_admin would choose), or None when the group would be
    deleted as user is its last member, or would be left waiting for someone
    to come back.
    """
    effects = []
    for own in Membership.objects.admins().filter(user=user).select_related("group"):
        group = own.group
        if group.memberships.admins().able_to_act().exclude(pk=own.pk).exists():
            continue
        others = group.memberships.active().exclude(pk=own.pk)
        successor = others.able_to_act().order_by("joined_at", "requested_at").select_related("user").first()
        effects.append({"group": group, "successor": successor, "closes": not others.exists()})
    return effects


def close(request, group):
    """Deletes a group that has no members left. Those waiting to join are told."""
    for pending in group.memberships.pending().select_related("user"):
        notifications.group_closed(request, pending.user, group)
    group.delete()


def edit_group(admin, group, name, description):
    require_admin(admin, group)
    group.name, group.description = name, description
    group.save(update_fields=["name", "description"])


def delete_group(request, admin, group):
    with transaction.atomic():
        group = lock(group)
        require_admin(admin, group)
        for membership in group.memberships.select_related("user").exclude(user=admin):
            notifications.group_deleted(request, admin, membership.user, group)
        for ride in group.rides.select_related("driver"):
            unpost(request, ride, group)
        group.delete()


# Rides

def unpost_rides(request, driver, group):
    """Takes group off the rides driver posted to it."""
    for ride in group.rides.filter(driver=driver).select_related("driver"):
        unpost(request, ride, group)


def unpost(request, ride, group):
    from rides.models import Ride
    ride.groups.remove(group)
    # A ride shown only to groups that are all gone is shown to nobody, not everyone
    if ride.groups_only and not ride.groups.exists() and Ride.objects.upcoming().filter(pk=ride.pk).exists():
        notifications.ride_hidden(request, ride, group)
