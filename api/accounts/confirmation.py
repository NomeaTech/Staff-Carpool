"""
Email confirmation for new accounts.

Signing up sends a link to the email address. Until it is opened and the
address confirmed, the account cannot log in (EmailBackend). Links expire
after PASSWORD_RESET_TIMEOUT (3 days by default) and work only once; a new
one can be sent from the login and "check your inbox" pages.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)

# A new link is sent at most this often per account
RESEND_DELAY = timedelta(seconds=60)


class EmailConfirmationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "accounts.confirmation.EmailConfirmationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        # Confirming changes email_confirmed_at, which makes the link stop working
        return f"{user.pk}{user.email}{user.email_confirmed_at}{timestamp}"


token_generator = EmailConfirmationTokenGenerator()


def send_confirmation(request, user):
    """
    Emails the user a link for confirming their address. Returns False when
    one was sent less than RESEND_DELAY ago, or the address is confirmed.
    """
    now = timezone.now()
    if user.email_confirmed_at or (user.confirmation_sent_at and now - user.confirmation_sent_at < RESEND_DELAY):
        return False

    path = reverse("confirm_email", args=[urlsafe_base64_encode(force_bytes(user.pk)), token_generator.make_token(user)])
    url = f"{settings.SITE_URL}{path}" if settings.SITE_URL else request.build_absolute_uri(path)
    body = render_to_string("registration/confirmation_email.txt", {"user": user, "url": url})
    subject = render_to_string("registration/confirmation_email_subject.txt").strip()
    try:
        send_mail(subject, body, None, [user.email])
    except Exception:
        logger.exception("Could not send the confirmation email to user %s", user.pk)
        return False

    user.confirmation_sent_at = now
    user.save(update_fields=["confirmation_sent_at"])
    return True
