"""
Changing a user's email address, without letting them lock themselves out:

- The user asks for the change on the profile page, with their password.
  The new address is kept as User.pending_email; the account keeps using
  its current address (for logging in, password resets and emails) until
  the new one is confirmed.
- A link is sent to the new address. Opening it and pressing the button
  switches the address, so a mistyped or unreachable address changes
  nothing. Links work once and expire after PASSWORD_RESET_TIMEOUT.
- The current address is told when a change is asked for and when it is
  done, so that a change the user did not make does not go unnoticed.
- The change can be cancelled, or the link sent again, until it is done.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

# A new link is sent at most this often per account
RESEND_DELAY = timedelta(seconds=60)


class EmailChangeTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "accounts.email_change.EmailChangeTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        # Changing, cancelling or completing the request makes the link stop working
        return f"{user.pk}{user.email}{user.pending_email}{timestamp}"


token_generator = EmailChangeTokenGenerator()


class EmailTaken(Exception):
    """The new address was taken by another account before it was confirmed."""


def address_taken(email, user):
    from .models import User
    return User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists()


def absolute_url(request, path):
    return f"{settings.SITE_URL}{path}" if settings.SITE_URL else request.build_absolute_uri(path)


def send(subject, template, to, **context):
    try:
        send_mail(subject, render_to_string(f"registration/{template}.txt", context), None, [to])
        return True
    except Exception:
        logger.exception("Could not send the %s email", template)
        return False


def request_change(request, user, new_email):
    """Starts changing the user's address to new_email (already checked by EmailChangeForm)."""
    user.pending_email = new_email
    user.pending_email_sent_at = None
    user.save(update_fields=["pending_email", "pending_email_sent_at"])
    send_link(request, user)
    send(_("Your LUT Kyyti email address is being changed"), "email_change_requested",
         user.email, user=user, new_email=new_email, account_url=absolute_url(request, reverse("account")))


def send_link(request, user):
    """
    Sends the confirmation link to the new address. Returns False when one
    was sent less than RESEND_DELAY ago, or no change is pending.
    """
    now = timezone.now()
    if not user.pending_email or (user.pending_email_sent_at and now - user.pending_email_sent_at < RESEND_DELAY):
        return False

    path = reverse("confirm_email_change", args=[urlsafe_base64_encode(force_bytes(user.pk)), token_generator.make_token(user)])
    if not send(_("Confirm your new LUT Kyyti email address"), "email_change_confirm",
                user.pending_email, user=user, url=absolute_url(request, path)):
        return False
    user.pending_email_sent_at = now
    user.save(update_fields=["pending_email_sent_at"])
    return True


def cancel(user):
    user.pending_email = ""
    user.pending_email_sent_at = None
    user.save(update_fields=["pending_email", "pending_email_sent_at"])


def complete(request, user):
    """Switches the account to its confirmed new address. Raises EmailTaken."""
    old_email, new_email = user.email, user.pending_email
    if address_taken(new_email, user):
        raise EmailTaken
    user.email = new_email
    user.pending_email = ""
    user.pending_email_sent_at = None
    # Opening the link proved the new address works
    user.email_confirmed_at = timezone.now()
    try:
        with transaction.atomic():
            user.save(update_fields=["email", "pending_email", "pending_email_sent_at", "email_confirmed_at"])
    except IntegrityError:
        raise EmailTaken
    send(_("Your LUT Kyyti email address was changed"), "email_changed",
         old_email, user=user, new_email=new_email, contact_url=absolute_url(request, reverse("contact")))
