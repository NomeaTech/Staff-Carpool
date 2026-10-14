from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

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
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone", "address", "pfp")}),
        (
            _("Privacy and notifications"),
            {"fields": ("name_visibility", "show_photo", "share_email", "share_phone", "notify_ride_requests")},
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
        (None, {"fields": ("phone", "address", "pfp")}),
    )

    def save_model(self, request, obj, form, change):
        # Accounts created by an admin need no email confirmation
        if not change and obj.email_confirmed_at is None:
            obj.email_confirmed_at = timezone.now()
        super().save_model(request, obj, form, change)

admin.site.register(User, CustomUserAdmin)
