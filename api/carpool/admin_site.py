from django.contrib import admin, messages
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _

from accounts import two_factor


class AdminSite(admin.AdminSite):
    """
    The admin, only for staff logged in with two-step verification
    (accounts/two_factor.py). It has no login page of its own: staff log in
    on the app's, which asks for the code, and come back here.
    """

    def has_permission(self, request):
        return super().has_permission(request) and request.user.is_verified()

    def login(self, request, extra_context=None):
        next_url = request.GET.get("next") or reverse("admin:index")
        user = request.user
        if user.is_authenticated:
            if not (user.is_active and user.is_staff):
                return redirect("home")
            if not two_factor.enabled(user):
                messages.info(request, _("Turn on two-step verification to use the admin."))
                return redirect(reverse("account") + "#two-step")
            # Logged in before two-step verification was turned on: log in
            # again, with the code
            logout(request)
        return redirect_to_login(next_url)
