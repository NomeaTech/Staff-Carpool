import csv

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from . import stats
from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import User

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    list_display = [
        "email",
        "first_name",
        "last_name",
    ]
    list_filter = ("is_active", "is_staff", ("email_confirmed_at", admin.EmptyFieldListFilter))
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)

    # Users log in with their email and have no username, so the default
    # UserAdmin fieldsets (which start with the username) are replaced
    fieldsets = (
        (None, {"fields": ("email", "pending_email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone", "pfp")}),
        (
            _("Privacy and notifications"),
            {"fields": ("name_visibility", "show_photo", "share_email", "share_phone", "email_notifications")},
        ),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined", "email_confirmed_at", "confirmation_sent_at")}),
    )
    readonly_fields = ("confirmation_sent_at", "pending_email")
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "usable_password", "password1", "password2"),
            },
        ),
        (None, {"fields": ("phone", "pfp")}),
    )

    def save_model(self, request, obj, form, change):
        # Accounts created by an admin need no email confirmation
        if not change and obj.email_confirmed_at is None:
            obj.email_confirmed_at = timezone.now()
        super().save_model(request, obj, form, change)

    # User statistics (accounts/stats.py), linked from the users list. For
    # admins who can view users, as the table and the CSV name them.
    def get_urls(self):
        return [
            path("stats/", self.admin_site.admin_view(self.stats_view), name="accounts_user_stats"),
            path("stats/users.csv", self.admin_site.admin_view(self.stats_csv_view), name="accounts_user_stats_csv"),
        ] + super().get_urls()

    def stats_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        form = stats.StatsFilterForm(request.GET or None)
        user_stats = stats.UserStats(form)
        sort = request.GET.get("sort", stats.DEFAULT_SORT)
        page = Paginator(user_stats.user_rows(sort), 50).get_page(request.GET.get("page"))

        def query(**changes):
            params = request.GET.copy()
            for key, value in changes.items():
                params[key] = value
            return params.urlencode()

        labels = {key: label for key, label, _value in stats.COLUMNS}
        values = {key: value for key, _label, value in stats.COLUMNS}
        current = sort if sort.lstrip("-") in stats.SORTS else stats.DEFAULT_SORT
        columns = [{
            "label": labels[key],
            # The first click sorts the most first; the next one reverses it
            "query": query(sort=key if current == f"-{key}" else f"-{key}", page=1),
            "sorted": "desc" if current == f"-{key}" else "asc" if current == key else "",
        } for key in stats.TABLE_COLUMNS]
        # The email and the dates are written out in the template; the rest are counts
        rows = [{"user": user, "cells": [values[key](user) for key in stats.TABLE_COLUMNS[3:]]} for user in page]

        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "title": _("User statistics"),
            "form": form,
            "stats": user_stats,
            "tiles": user_stats.tiles(),
            "charts": user_stats.charts(),
            "routes": user_stats.top_routes(),
            "retention": user_stats.retention(),
            "retention_months": stats.RETENTION_MONTHS,
            "columns": columns,
            "rows": rows,
            "page": page,
            "previous_query": query(page=page.previous_page_number()) if page.has_previous() else "",
            "next_query": query(page=page.next_page_number()) if page.has_next() else "",
            "csv_query": request.GET.urlencode(),
            "metabase_url": settings.METABASE_URL,
        }
        return TemplateResponse(request, "admin/accounts/user_stats.html", context)

    def stats_csv_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        user_stats = stats.UserStats(stats.StatsFilterForm(request.GET or None))
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="users-{timezone.localdate():%Y-%m-%d}.csv"'
        # A byte order mark, for Excel to read the file as UTF-8
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow([key for key, _label, _value in stats.COLUMNS])
        for user in user_stats.user_rows("date_joined").iterator():
            writer.writerow([csv_cell(value(user)) for _key, _label, value in stats.COLUMNS])
        return response


def csv_cell(value):
    """
    A value for the CSV. Text that a spreadsheet would run as a formula
    (a name such as "=HYPERLINK(...)" chosen by a user) starts with an
    apostrophe instead, so that it is shown as text.
    """
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value

admin.site.register(User, CustomUserAdmin)
