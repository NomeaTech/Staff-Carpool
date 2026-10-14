from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import CreateView

from home import notifications
from .forms import SignUpForm, UserLoginForm, ProfileForm, SettingsForm, PhotoForm, DeleteAccountForm, PHOTO_MAX_UPLOAD, photo_too_large
from .models import User, delete_photo_file
from .privacy import can_see_photo

class SignUpView(CreateView):
    form_class = SignUpForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"

class UserLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = UserLoginForm
    # Users who are already logged in skip the login page. They are sent to
    # ?next= if it is a safe URL, otherwise to LOGIN_REDIRECT_URL (/app/home/).
    redirect_authenticated_user = True

    def get_redirect_url(self):
        # Only follow ?next= to pages in the app, e.g. a shared ride. Logging
        # in from the landing pages (?next=/, /faq, ...) goes to /app/home/.
        url = super().get_redirect_url()
        return url if url.startswith("/app/") else ""

def LogoutView(request):
    logout(request)

@login_required
def account(request):
    """
    The profile & settings page. Its forms are posted here, each with a
    "form" field naming it, and the page is shown again with the others
    unbound.
    """
    user = request.user
    posted = request.POST.get("form") if request.method == "POST" else None
    data = lambda name: (request.POST, request.FILES) if posted == name else (None,)

    profile_form = ProfileForm(*data("profile"), instance=user, prefix="profile")
    settings_form = SettingsForm(*data("settings"), instance=user, prefix="settings")
    photo_form = PhotoForm(*data("photo"), prefix="photo")
    delete_form = DeleteAccountForm(user, *data("delete"), prefix="delete")

    if posted == "profile" and profile_form.is_valid():
        profile_form.save()
        messages.success(request, _("Your profile was saved."))
        return redirect("account")
    if posted == "settings" and settings_form.is_valid():
        settings_form.save()
        messages.success(request, _("Your settings were saved."))
        return redirect("account")
    if posted == "photo" and photo_form.is_valid():
        photo_form.save(user)
        messages.success(request, _("Your photo was changed."))
        return redirect("account")
    if posted == "remove_photo" and user.pfp:
        # User.save() deletes the file
        user.pfp = None
        user.save(update_fields=["pfp"])
        messages.success(request, _("Your photo was removed."))
        return redirect("account")
    if posted == "delete" and delete_form.is_valid():
        with transaction.atomic():
            # Everyone in the rides the user drives is told they are cancelled
            for ride in user.driver.all():
                notifications.ride_cancelled(request, ride)
            photo = user.pfp.name if user.pfp else None
            logout(request)
            user.delete()
        delete_photo_file(photo)
        return redirect("landing")

    context = {
        "profile_form": profile_form,
        "settings_form": settings_form,
        "photo_form": photo_form,
        "delete_form": delete_form,
        "photo_max_upload": PHOTO_MAX_UPLOAD,
        "photo_too_large": photo_too_large(),
    }
    return render(request, "registration/account.html", context)

@login_required
def photo(request, user_id):
    """A member's profile photo, for those allowed to see it (see accounts/privacy.py)."""
    user = get_object_or_404(User, pk=user_id)
    if not can_see_photo(user, request.user):
        raise Http404
    try:
        response = FileResponse(user.pfp.open("rb"), content_type="image/jpeg")
    except FileNotFoundError:
        raise Http404
    # Only the browser may keep a copy, as the photo is not public. A new
    # photo has a new URL (?v=<file name>, see the avatar tag), so the copy
    # never needs checking: the browser keeps using it across pages.
    response["Cache-Control"] = "private, max-age=31536000, immutable"
    return response
