from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.generic import CreateView

from notifications import services as notifications
from test_app.models import RideRequest
from .forms import SignUpForm, UserLoginForm, ProfileForm, SettingsForm, PhotoForm, DeleteAccountForm, EmailChangeForm, PHOTO_MAX_UPLOAD, photo_too_large
from . import email_change
from .confirmation import send_confirmation, token_generator
from .models import User, delete_photo_file
from .privacy import can_see_photo

class SignUpView(CreateView):
    """
    New accounts cannot log in until their email address is confirmed: the
    user is sent a link and shown the "check your inbox" page.
    """
    form_class = SignUpForm
    template_name = "registration/signup.html"

    def form_valid(self, form):
        user = form.save()
        send_confirmation(self.request, user)
        return confirmation_sent_redirect(self.request, user.email)

    def form_invalid(self, form):
        if form.unconfirmed_user:
            send_confirmation(self.request, form.unconfirmed_user)
            self.request.session["confirmation_email"] = form.unconfirmed_user.email
        return super().form_invalid(form)

def confirmation_sent_redirect(request, email):
    # The address is kept in the session, not the URL, so it is not logged
    request.session["confirmation_email"] = email
    return redirect("confirmation_sent")

def confirmation_sent(request):
    """The "check your inbox" page, with a button for sending a new link."""
    email = request.session.get("confirmation_email")
    if not email:
        return redirect("login")
    return render(request, "registration/confirmation_sent.html", {
        "email": email,
        "resent": request.GET.get("resent") == "1",
    })

@require_POST
def resend_confirmation(request):
    """
    Sends a new confirmation link. The page says the same whether or not the
    address has an unconfirmed account, so it does not reveal which do.
    """
    email = request.POST.get("email", "").strip()
    user = User.objects.filter(email__iexact=email, email_confirmed_at__isnull=True, is_active=True).first() if email else None
    if user:
        send_confirmation(request, user)
    request.session["confirmation_email"] = email
    return redirect(f"{reverse('confirmation_sent')}?resent=1")

def confirm_email(request, uidb64, token):
    """
    The link in the confirmation email. Opening it shows a button that
    confirms the address and logs the user in: confirming only on a POST
    means email security scanners that open links do not use them up.
    """
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, ValidationError):
        user = None

    valid = user is not None and token_generator.check_token(user, token)
    if not valid:
        already_confirmed = user is not None and user.email_confirmed_at is not None
        return render(request, "registration/confirm_email.html", {"invalid": True, "already_confirmed": already_confirmed}, status=400)

    if request.method == "POST":
        user.email_confirmed_at = timezone.now()
        user.save(update_fields=["email_confirmed_at"])
        request.session.pop("confirmation_email", None)
        if user.is_active:
            login(request, user, backend="accounts.backends.EmailBackend")
            messages.success(request, _("Your email address is confirmed. Welcome to LUT Kyyti!"))
            return redirect("home")
        return redirect("login")

    return render(request, "registration/confirm_email.html", {"email": user.email})

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
    email_form = EmailChangeForm(user, *data("email"), prefix="email")

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
    if posted == "email" and email_form.is_valid():
        email_change.request_change(request, user, email_form.cleaned_data["new_email"])
        messages.success(request, _("We sent a confirmation link to %(email)s. Your email address changes once you open it.") % {"email": user.pending_email})
        return redirect("account")
    if posted == "email_resend" and user.pending_email:
        if email_change.send_link(request, user):
            messages.success(request, _("We sent a new confirmation link to %(email)s.") % {"email": user.pending_email})
        else:
            messages.info(request, _("A link was sent less than a minute ago. Wait a moment before asking for a new one."))
        return redirect("account")
    if posted == "email_cancel" and user.pending_email:
        email_change.cancel(user)
        messages.success(request, _("The email change was cancelled. Your address stays %(email)s.") % {"email": user.email})
        return redirect("account")
    if posted == "delete" and delete_form.is_valid():
        with transaction.atomic():
            # Everyone in the rides the user drives is told they are
            # cancelled, and the drivers of rides they joined or requested
            # that they left
            for ride in user.driver.all():
                notifications.ride_cancelled(request, ride)
            for ride_request in user.ride_requests.select_related("ride__driver"):
                if ride_request.status == RideRequest.Status.ACCEPTED:
                    notifications.passenger_left(request, ride_request)
                elif ride_request.status == RideRequest.Status.PENDING:
                    notifications.request_withdrawn(request, ride_request)
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
        "email_form": email_form,
        "photo_max_upload": PHOTO_MAX_UPLOAD,
        "photo_too_large": photo_too_large(),
    }
    return render(request, "registration/account.html", context)

def confirm_email_change(request, uidb64, token):
    """
    The link sent to a new email address. Opening it shows a button that
    switches the account to the address (POST only, so that email scanners
    opening the link do not use it up). It works without logging in: the
    change was asked for with the password, and the link proves the new
    address works.
    """
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, ValidationError):
        user = None

    if user is None or not user.pending_email or not email_change.token_generator.check_token(user, token):
        return render(request, "registration/confirm_email_change.html", {"invalid": True}, status=400)

    if request.method == "POST":
        new_email = user.pending_email
        try:
            email_change.complete(request, user)
        except email_change.EmailTaken:
            email_change.cancel(user)
            return render(request, "registration/confirm_email_change.html", {"taken": True, "email": new_email}, status=409)
        if request.user.is_authenticated and request.user.pk == user.pk:
            messages.success(request, _("Your email address is now %(email)s.") % {"email": new_email})
            return redirect("account")
        return render(request, "registration/confirm_email_change.html", {"done": True, "email": new_email})

    return render(request, "registration/confirm_email_change.html", {"email": user.pending_email, "old_email": user.email})

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
