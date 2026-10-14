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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailChangeTests(TestCase):
    def setUp(self):
        self.user = make_user("Jamie", "Saarinen")
        self.client.force_login(self.user)
        self.url = reverse("account")

    def ask(self, new_email="jamie.new@lut.fi", password="Passw0rd!x"):
        response = self.client.post(self.url, {"form": "email", "email-new_email": new_email, "email-password": password})
        self.user.refresh_from_db()
        return response

    def link(self):
        mail_to_new = [m for m in mail.outbox if m.to == [self.user.pending_email or "jamie.new@lut.fi"]][-1]
        return re.search(r"https?://\S+(/app/accounts/email/\S+/)", mail_to_new.body).group(1)

    def log_in(self, email):
        client = self.client_class()
        return client.post(reverse("login"), {"username": email, "password": "Passw0rd!x"}).status_code == 302

    def test_address_changes_only_once_confirmed(self):
        self.ask()
        self.assertEqual(self.user.email, "jamie@lut.fi")
        self.assertEqual(self.user.pending_email, "jamie.new@lut.fi")
        # A link to the new address, and a notice to the current one
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["jamie.new@lut.fi", "jamie@lut.fi"])

        # Until then, the current address still logs in
        self.assertTrue(self.log_in("jamie@lut.fi"))
        self.assertFalse(self.log_in("jamie.new@lut.fi"))

        link = self.link()
        self.assertContains(self.client.get(link), "Confirm new address")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "jamie@lut.fi")

        self.assertRedirects(self.client.post(link), self.url, fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual((self.user.email, self.user.pending_email), ("jamie.new@lut.fi", ""))
        self.assertTrue(self.log_in("jamie.new@lut.fi"))
        self.assertTrue(self.log_in("Jamie.New@LUT.fi"))
        self.assertFalse(self.log_in("jamie@lut.fi"))
        # The old address is told
        self.assertIn("was changed to jamie.new@lut.fi", mail.outbox[-1].body)
        self.assertEqual(mail.outbox[-1].to, ["jamie@lut.fi"])

        # The link works once
        self.assertEqual(self.client.post(link).status_code, 400)

    def test_link_works_without_logging_in(self):
        self.ask()
        link = self.link()
        self.client.logout()
        response = self.client.post(link)
        self.assertContains(response, "Your email address is now")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "jamie.new@lut.fi")

    def test_requests_are_checked(self):
        make_user("Aino", "Mäkinen")
        for new_email, password, message in [
            ("jamie.new@lut.fi", "wrong", "The password is incorrect."),
            ("jamie@gmail.com", "Passw0rd!x", "Use your LUT or LAB email address"),
            ("JAMIE@lut.fi", "Passw0rd!x", "This is already your email address."),
            ("Aino@lut.fi", "Passw0rd!x", "Another account already uses this email address."),
            ("not an address", "Passw0rd!x", "Enter a valid email address."),
        ]:
            with self.subTest(new_email=new_email):
                self.assertContains(self.ask(new_email, password), message)
                self.assertEqual(self.user.pending_email, "")
        self.assertEqual(len(mail.outbox), 0)

    def test_new_address_is_saved_in_lower_case(self):
        self.ask("Jamie.New@LAB.fi")
        self.assertEqual(self.user.pending_email, "jamie.new@lab.fi")

    def test_cancelling_keeps_the_address_and_stops_the_link(self):
        self.ask()
        link = self.link()
        self.client.post(self.url, {"form": "email_cancel"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.pending_email, "")
        self.assertEqual(self.client.post(link).status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "jamie@lut.fi")

    def test_asking_again_replaces_the_link(self):
        self.ask()
        first = self.link()
        self.ask("jamie.other@lut.fi")
        self.assertEqual(self.client.post(first).status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "jamie@lut.fi")

    def test_resending_is_rate_limited(self):
        self.ask()
        sent = len(mail.outbox)
        self.client.post(self.url, {"form": "email_resend"})
        self.assertEqual(len(mail.outbox), sent)
        User.objects.filter(pk=self.user.pk).update(pending_email_sent_at=timezone.now() - timedelta(minutes=2))
        self.client.post(self.url, {"form": "email_resend"})
        self.assertEqual(len(mail.outbox), sent + 1)

    def test_address_taken_in_the_meantime(self):
        self.ask()
        link = self.link()
        make_user("Other", "Person").__class__.objects.filter(email="other@lut.fi").update(email="jamie.new@lut.fi")
        response = self.client.post(link)
        self.assertContains(response, "is now used by another account", status_code=409)
        self.user.refresh_from_db()
        self.assertEqual((self.user.email, self.user.pending_email), ("jamie@lut.fi", ""))

    def test_profile_page_shows_the_pending_change(self):
        self.ask()
        response = self.client.get(self.url)
        self.assertContains(response, "Waiting for you to confirm")
        self.assertContains(response, 'form="email-cancel-form"')
