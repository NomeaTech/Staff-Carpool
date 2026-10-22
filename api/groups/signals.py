"""
Runs services.ensure_admin whenever a group could be left without an admin
who can act, however it happens: in the app, in Django's admin, or when an
account is deleted (its memberships go with it).
"""
from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Group, Membership
from .services import ensure_admin


@receiver(post_save, sender=Membership)
def membership_saved(sender, instance, **kwargs):
    ensure_admin(instance.group)


@receiver(post_delete, sender=Membership)
def membership_deleted(sender, instance, origin=None, **kwargs):
    # Not when the group itself is being deleted, which deletes its memberships
    if isinstance(origin, Group) or getattr(origin, "model", None) is Group:
        return
    ensure_admin(instance.group)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def account_changed(sender, instance, **kwargs):
    """
    An account that cannot be used any more: blocked by a staff admin, or its
    email address no longer confirmed (e.g. not confirmed again after leaving
    LUT/LAB). Its groups get another admin; it stays a member and keeps its
    role, in case it comes back.
    """
    if instance.is_active and instance.email_confirmed_at is not None:
        return
    for membership in Membership.objects.admins().filter(user=instance).select_related("group"):
        ensure_admin(membership.group)


@receiver(post_save, sender="activity.Event")
def member_came_back(sender, instance, created, **kwargs):
    """
    A member's first visit of the day (activity/middleware.py): their groups
    that have no admin who can act get one, so a group whose people were all
    away has an admin again as soon as one of them comes back.
    """
    from activity.models import Kind
    if not created or instance.kind != Kind.ACTIVE or instance.user_id is None:
        return
    for membership in Membership.objects.active().filter(user_id=instance.user_id).select_related("group"):
        if not membership.group.memberships.admins().able_to_act().exists():
            ensure_admin(membership.group)
