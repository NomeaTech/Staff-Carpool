from django.contrib import admin
from django.db.models import Count, Exists, OuterRef, Q
from django.utils.translation import gettext_lazy as _

from .models import Group, Membership


class MembershipInline(admin.TabularInline):
    model = Membership
    raw_id_fields = ("user",)
    fields = ("user", "status", "role", "requested_at", "joined_at")
    readonly_fields = ("requested_at",)
    extra = 0


class NeedsAdminFilter(admin.SimpleListFilter):
    """
    Groups where nobody can answer requests: no admin who can act, and no
    member who can act to become one (groups/services.py ensure_admin). A
    staff admin can make one of its members admin here.
    """
    title = _("admin")
    parameter_name = "needs_admin"

    def lookups(self, request, model_admin):
        return [("yes", _("Has no admin who can act"))]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            able = Membership.objects.admins().able_to_act().filter(group=OuterRef("pk"))
            return queryset.exclude(Exists(able))
        return queryset


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "members", "admins", "waiting", "created_at")
    list_filter = (NeedsAdminFilter,)
    search_fields = ("name",)
    readonly_fields = ("created_by", "created_at")
    inlines = [MembershipInline]

    def get_queryset(self, request):
        active = Q(memberships__status=Membership.Status.ACTIVE)
        return super().get_queryset(request).annotate(
            member_count=Count("memberships", filter=active),
            admin_count=Count("memberships", filter=active & Q(memberships__role=Membership.Role.ADMIN)),
            waiting_count=Count("memberships", filter=Q(memberships__status=Membership.Status.PENDING)),
        )

    @admin.display(description=_("members"), ordering="member_count")
    def members(self, group):
        return group.member_count

    @admin.display(description=_("admins"), ordering="admin_count")
    def admins(self, group):
        return group.admin_count

    @admin.display(description=_("requests to join"), ordering="waiting_count")
    def waiting(self, group):
        return group.waiting_count
