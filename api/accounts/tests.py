import re
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from home.tests import make_user
from .models import User


SIGNUP = {
    "email": "jamie.saarinen@lut.fi",
    "first_name": "Jamie",
    "last_name": "Saarinen",
    "password1": "Kyyti-Passw0rd",
    "password2": "Kyyti-Passw0rd",
}


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailConfirmationTests(TestCase):
    def sign_up(self, **fields):
        return self.client.post(reverse("signup"), {**SIGNUP, **fields})

    def log_in(self, password=SIGNUP["password1"]):
        return self.client.post(reverse("login"), {"username": SIGNUP["email"], "password": password})

    def confirmation_link(self, index=-1):
        return re.search(r"https?://\S+(/app/accounts/confirm/\S+/)", mail.outbox[index].body).group(1)

    def test_signup_sends_a_link_and_the_account_waits_for_it(self):
        response = self.sign_up()
        self.assertRedirects(response, reverse("confirmation_sent"))
        self.assertContains(self.client.get(reverse("confirmation_sent")), SIGNUP["email"])

        user = User.objects.get(email=SIGNUP["email"])
        self.assertIsNone(user.email_confirmed_at)
        self.assertEqual(mail.outbox[0].to, [SIGNUP["email"]])

        # Cannot log in, and is told why
        response = self.log_in()
        self.assertContains(response, "Confirm your email address before logging in.")
        self.assertContains(response, reverse("resend_confirmation"))
        self.assertEqual(self.client.get(reverse("home")).status_code, 302)

    def test_wrong_password_does_not_reveal_an_unconfirmed_account(self):
        self.sign_up()
        response = self.log_in(password="wrong")
        self.assertNotContains(response, "Confirm your email address")
        self.assertContains(response, "Enter a valid email and password")

    def test_confirming_logs_in_and_the_link_works_once(self):
        self.sign_up()
        link = self.confirmation_link()

        # Opening the link (e.g. an email scanner) does not confirm by itself
        self.assertContains(self.client.get(link), "Confirm and log in")
        self.assertIsNone(User.objects.get().email_confirmed_at)

        response = self.client.post(link)
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertIsNotNone(User.objects.get().email_confirmed_at)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

        self.client.logout()
        response = self.client.get(link)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "already confirmed", status_code=400)
        self.assertRedirects(self.log_in(), reverse("home"), fetch_redirect_response=False)

    def test_invalid_and_expired_links(self):
        self.sign_up()
        link = self.confirmation_link()
        self.assertEqual(self.client.post(link[:-3] + "xx/").status_code, 400)
        self.assertEqual(self.client.get("/app/accounts/confirm/bm9wZQ/abc-def/").status_code, 400)
        with self.settings(PASSWORD_RESET_TIMEOUT=-1):
            response = self.client.post(link)
        self.assertContains(response, "invalid or has expired", status_code=400)
        self.assertIsNone(User.objects.get().email_confirmed_at)

    def test_resending_is_rate_limited(self):
        self.sign_up()
        resend = lambda: self.client.post(reverse("resend_confirmation"), {"email": SIGNUP["email"]})
        self.assertRedirects(resend(), reverse("confirmation_sent") + "?resent=1")
        self.assertEqual(len(mail.outbox), 1)

        User.objects.update(confirmation_sent_at=timezone.now() - timedelta(minutes=2))
        resend()
        self.assertEqual(len(mail.outbox), 2)
        # The newest link works
        self.client.post(self.confirmation_link())
        self.assertIsNotNone(User.objects.get().email_confirmed_at)

    def test_resend_does_not_reveal_accounts(self):
        make_user("Aino", "Mäkinen")
        for email in ["nobody@lut.fi", "aino@lut.fi"]:
            response = self.client.post(reverse("resend_confirmation"), {"email": email}, follow=True)
            self.assertContains(response, f"If {email} has an account waiting for confirmation")
        self.assertEqual(len(mail.outbox), 0)

    def test_signing_up_again_resends_the_link(self):
        self.sign_up()
        User.objects.update(confirmation_sent_at=timezone.now() - timedelta(minutes=2))
        response = self.sign_up(email=SIGNUP["email"].upper())
        self.assertContains(response, "has not been confirmed yet")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)

        make_user("Aino", "Mäkinen")
        response = self.sign_up(email="aino@lut.fi")
        self.assertContains(response, "An account with this email address already exists.")

    def test_blocked_accounts_cannot_log_in(self):
        user = make_user("Aino", "Mäkinen", is_active=False)
        response = self.client.post(reverse("login"), {"username": user.email, "password": "Passw0rd!x"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Confirm your email address")

    def test_existing_and_admin_accounts_are_confirmed(self):
        user = make_user("Aino", "Mäkinen")
        response = self.client.post(reverse("login"), {"username": user.email, "password": "Passw0rd!x"})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

        superuser = User.objects.create_superuser(username="admin", email="admin@lut.fi", password="x")
        self.assertIsNotNone(superuser.email_confirmed_at)

        self.client.force_login(superuser)
        self.client.post(reverse("admin:accounts_user_add"), {
            "email": "new@lut.fi", "first_name": "New", "last_name": "Member", "usable_password": "true",
            "password1": "Kyyti-Passw0rd", "password2": "Kyyti-Passw0rd",
        })
        self.assertIsNotNone(User.objects.get(email="new@lut.fi").email_confirmed_at)
