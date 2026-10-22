from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from rides.models import Ride
from . import services
from .forms import GroupForm
from .models import Group, Membership


@login_required
def group_list(request):
    """The user's groups, their requests to join, the other groups, and making a group."""
    user = request.user
    form = GroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        group = services.create_group(user, form.cleaned_data["name"], form.cleaned_data["description"])
        messages.success(request, _("The group %(name)s was made. You are its admin.") % {"name": group.name})
        return redirect("group_detail", group_id=group.pk)

    mine = (Membership.objects.filter(user=user).select_related("group")
            .annotate(members=Count("group__memberships", filter=Q(group__memberships__status=Membership.Status.ACTIVE)),
                      waiting=Count("group__memberships", filter=Q(group__memberships__status=Membership.Status.PENDING)))
            .order_by("status", "group__name"))
    query = request.GET.get("q", "").strip()
    others = (Group.objects.exclude(memberships__user=user)
              .annotate(members=Count("memberships", filter=Q(memberships__status=Membership.Status.ACTIVE))))
    if query:
        others = others.filter(name__icontains=query)
    return render(request, "groups/list.html", {
        "member_of": [m for m in mine if m.status == Membership.Status.ACTIVE],
        "asked": [m for m in mine if m.status == Membership.Status.PENDING],
        "others": others[:50],
        "query": query,
        "form": form,
        "show_form": request.method == "POST",
    })


@login_required
def group_detail(request, group_id):
    """
    A group's page. Everyone sees its name, description and admins, and can
    ask to join; members see the members and the rides posted to it; admins
    answer requests and manage the group. Its forms are posted here, each
    with an "action".
    """
    group = get_object_or_404(Group, pk=group_id)
    user = request.user
    membership = services.membership_of(user, group)

    if request.method == "POST":
        try:
            done = act(request, group, membership, request.POST.get("action"))
        except services.GroupError as error:
            messages.error(request, str(error))
            done = None
        if done == "deleted":
            return redirect("groups")
        if isinstance(done, GroupForm):
            return render_group(request, group, membership, edit_form=done)
        return redirect("group_detail", group_id=group.pk)

    if membership and membership.status == Membership.Status.ACTIVE:
        # A group whose admins are all away gets one when its members look at it
        services.ensure_admin(group, request)
        membership.refresh_from_db()
        # Seeing the group is seeing what its notifications were about
        user.notifications.filter(group=group, read_at__isnull=True).update(read_at=timezone.now())
    return render_group(request, group, membership)


def act(request, group, membership, action):
    user = request.user
    other = lambda: get_object_or_404(Membership, pk=request.POST.get("membership"), group=group)

    if action == "join":
        if services.request_to_join(request, user, group):
            messages.success(request, _("Request sent. You will be notified when an admin answers."))
    elif action == "cancel":
        services.cancel_request(user, group)
        messages.success(request, _("Your request was withdrawn."))
    elif action == "leave":
        successor = Membership.objects.filter(pk=request.POST.get("successor") or None, group=group).first()
        services.leave(request, user, group, successor)
        messages.success(request, _("You left %(name)s.") % {"name": group.name})
        return "deleted" if not Group.objects.filter(pk=group.pk).exists() else "left"
    elif action in ("accept", "decline"):
        services.answer_request(request, user, other(), accept=action == "accept")
    elif action == "make_admin":
        services.make_admin(request, user, other())
        messages.success(request, _("They are now an admin."))
    elif action == "hand_over":
        services.hand_over(request, user, other())
        messages.success(request, _("You handed the admin role over."))
    elif action == "step_down":
        services.step_down(user, group)
        messages.success(request, _("You are no longer an admin."))
    elif action == "remove":
        services.remove_member(request, user, other())
        messages.success(request, _("The member was removed."))
    elif action == "edit":
        services.require_admin(user, group)
        form = GroupForm(request.POST, instance=Group.objects.get(pk=group.pk))
        if not form.is_valid():
            return form
        services.edit_group(user, group, form.cleaned_data["name"], form.cleaned_data["description"])
        messages.success(request, _("The group was saved."))
    elif action == "delete":
        services.delete_group(request, user, group)
        messages.success(request, _("The group %(name)s was deleted.") % {"name": group.name})
        return "deleted"
    return "done"


def render_group(request, group, membership, edit_form=None):
    is_member = membership is not None and membership.status == Membership.Status.ACTIVE
    is_admin = membership is not None and membership.is_admin
    # Admins first, then the others, each in the order they joined
    members = sorted(group.memberships.active().select_related("user"), key=lambda m: not m.is_admin)
    able = set(group.memberships.able_to_act().values_list("pk", flat=True))
    context = {
        "group": group,
        "membership": membership,
        "is_member": is_member,
        "is_admin": is_admin,
        "admins": [m for m in members if m.role == Membership.Role.ADMIN],
        "member_count": len(members),
    }
    if is_member:
        context["members"] = [(m, m.pk in able) for m in members]
        context["rides"] = Ride.objects.upcoming().filter(groups=group).select_related("driver").with_seats_taken()
        others = [m for m in members if m.pk != membership.pk]
        # Who can take over: members who can act (services.make_admin)
        context["successors"] = [m for m in others if m.pk in able and m.role != Membership.Role.ADMIN]
        if is_admin:
            other_admins = [m for m in others if m.role == Membership.Role.ADMIN and m.pk in able]
            context["only_admin"] = not other_admins
            context["last_member"] = not others
            context["requests"] = group.memberships.pending().select_related("user").filter(
                user__is_active=True, user__email_confirmed_at__isnull=False)
            context["edit_form"] = edit_form or GroupForm(instance=group)
    return render(request, "groups/detail.html", context)
