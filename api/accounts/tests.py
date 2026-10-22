import re
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from home.tests import make_user, log_in_to_admin
from . import two_factor
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

        log_in_to_admin(self.client, superuser)
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


class SignUpValidationTests(TestCase):
    """What the sign up page says is wrong, under the field it is about."""

    def errors(self, **fields):
        response = self.client.post(reverse("signup"), {**SIGNUP, **fields})
        form = response.context["form"] if response.context else None
        return {name: list(errors) for name, errors in form.errors.items()} if form else {}

    def test_messages_name_the_problem(self):
        make_user("Aino", "Mäkinen")
        cases = [
            ({"email": "aino@lut.fi"}, "email", "An account with this email address already exists."),
            ({"email": "AINO@LUT.FI"}, "email", "An account with this email address already exists."),
            ({"email": "jamie@gmail.com"}, "email", "Use your LUT or LAB email address"),
            ({"email": "jamie"}, "email", "Enter a valid email address"),
            ({"email": ""}, "email", "Enter your LUT or LAB email address."),
            ({"first_name": ""}, "first_name", "Enter your first name."),
            ({"last_name": "S" * 51}, "last_name", "Your last name can be at most 50 characters."),
            ({"password1": ""}, "password1", "Choose a password."),
            ({"password2": "Kyyti-Passw0rd2"}, "password2", "The passwords don't match."),
            ({"password1": "Ky-0a", "password2": "Ky-0a"}, "password1", "This password is too short."),
            ({"password1": "kyyti-password", "password2": "kyyti-password"}, "password1",
             "Your password must also contain a number and an upper case letter."),
            ({"password1": "Saarinen2026", "password2": "Saarinen2026"}, "password1", "too similar to the last name"),
        ]
        for fields, field, message in cases:
            with self.subTest(fields=fields):
                errors = self.errors(**fields)
                self.assertIn(field, errors)
                self.assertTrue(any(message in error for error in errors[field]), errors[field])
        self.assertEqual(User.objects.count(), 1)

    def test_page_shows_errors_under_their_fields(self):
        response = self.client.post(reverse("signup"), {**SIGNUP, "email": "jamie@gmail.com", "first_name": ""})
        page = response.content.decode()
        self.assertIn('id="id_email-errors"', page)
        self.assertIn('aria-invalid="true"', page)
        self.assertIn("Enter your first name.", page)
        # No bare field names
        self.assertNotIn("<li>email</li>", page)

    def test_email_is_saved_in_lower_case(self):
        self.client.post(reverse("signup"), {**SIGNUP, "email": "Jamie.Saarinen@LUT.fi"})
        self.assertTrue(User.objects.filter(email="jamie.saarinen@lut.fi").exists())

    def test_browser_checks_are_on_the_fields(self):
        page = self.client.get(reverse("signup")).content.decode()
        self.assertIn('pattern="[^@\\s]+@([Ll][Uu][Tt]|[Ll][Aa][Bb])\\.[Ff][Ii]"', page)
        self.assertIn('pattern="(?=.*\\p{Nd})(?=.*\\p{Ll})(?=.*\\p{Lu}).{8,}"', page)
        self.assertIn('maxlength="50"', page)
        self.assertIn('data-mismatch=', page)


class UserStatsTests(TestCase):
    """The admin's user statistics (accounts/stats.py) and their CSV."""

    def setUp(self):
        from home.tests import make_ride
        from rides.models import RideRequest
        self.admin = make_user("Ada", "Admin", is_staff=True, is_superuser=True)
        self.driver = make_user("Aino", "Mäkinen")
        self.passenger = make_user("Jamie", "Saarinen")
        User.objects.filter(pk=self.passenger.pk).update(email="jamie.saarinen@lab.fi")
        ride = make_ride(self.driver)
        RideRequest.objects.create(ride=ride, passenger=self.passenger, status=RideRequest.Status.ACCEPTED)
        log_in_to_admin(self.client, self.admin)

    def csv_rows(self, **params):
        response = self.client.get(reverse("admin:accounts_user_stats_csv"), params)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        lines = response.content.decode("utf-8-sig").splitlines()
        header = lines[0].split(",")
        return {row["email"]: row for row in (dict(zip(header, line.split(","))) for line in lines[1:])}

    def test_page_shows_numbers_charts_and_users(self):
        response = self.client.get(reverse("admin:accounts_user_stats"))
        self.assertContains(response, 'id="stats-charts"')
        self.assertContains(response, 'data-chart="activity"')
        self.assertContains(response, "jamie.saarinen@lab.fi")
        self.assertContains(response, "Lappeenranta")
        # The users list links to it
        self.assertContains(self.client.get(reverse("admin:accounts_user_changelist")), reverse("admin:accounts_user_stats"))

    def test_csv_counts_each_users_activity(self):
        rows = self.csv_rows()
        driver, passenger = rows[self.driver.email], rows["jamie.saarinen@lab.fi"]
        self.assertEqual((driver["rides_posted"], driver["requests_received"], driver["requests_received_accepted"]), ("1", "1", "1"))
        self.assertEqual((passenger["requests_made"], passenger["requests_accepted"], passenger["domain"]), ("1", "1", "lab.fi"))

    def test_filters(self):
        self.assertEqual(set(self.csv_rows(domain="lab.fi")), {"jamie.saarinen@lab.fi"})
        # Activity before the period is not counted
        from rides.models import Ride
        Ride.objects.update(created_at=timezone.now() - timedelta(days=60))
        self.assertEqual(self.csv_rows(period="30")[self.driver.email]["rides_posted"], "0")
        self.assertEqual(self.csv_rows(period="90")[self.driver.email]["rides_posted"], "1")
        # Users who joined after the period are left out
        last_week = timezone.localdate() - timedelta(days=7)
        self.assertEqual(self.csv_rows(period="custom", start=last_week, end=last_week), {})
        # An invalid range shows an error and the defaults
        response = self.client.get(reverse("admin:accounts_user_stats"), {"period": "custom", "start": "2026-02-01", "end": "2026-01-01"})
        self.assertContains(response, "The start of the period is after its end.")

    def test_test_user_and_test_rides_are_left_out(self):
        from home.tests import make_ride
        from notifications.models import Notification
        from rides.admin import TEST_RIDE_KEY, test_user
        from rides.models import RideRequest
        from accounts.stats import StatsFilterForm, UserStats
        tester = test_user()
        place = {"displayName": "Imatra", TEST_RIDE_KEY: True, "location": {"lat": 61.2, "lng": 28.8}}
        test_rides = [make_ride(tester), make_ride(self.driver, start_json=place)]
        for ride in test_rides:
            RideRequest.objects.create(ride=ride, passenger=self.passenger, status=RideRequest.Status.ACCEPTED)
            Notification.objects.create(recipient=self.passenger, kind=Notification._meta.get_field("kind").choices[0][0], ride=ride)
        # A notification without a ride still counts
        Notification.objects.create(recipient=self.passenger, kind=Notification._meta.get_field("kind").choices[0][0])

        rows = self.csv_rows()
        self.assertNotIn(tester.email, rows)
        self.assertEqual(rows[self.driver.email]["rides_posted"], "1")
        self.assertEqual(rows[self.driver.email]["requests_received"], "1")
        passenger = rows["jamie.saarinen@lab.fi"]
        self.assertEqual((passenger["requests_made"], passenger["requests_accepted"], passenger["notifications_received"]), ("1", "1", "1"))

        stats = UserStats(StatsFilterForm())
        self.assertEqual(stats.users.count(), 3)
        self.assertEqual(stats.rides.count(), 1)
        self.assertEqual(stats.requests.count(), 1)
        self.assertEqual([route[:2] for route in stats.top_routes()], [("Lappeenranta", "Lahti")])
        self.assertNotContains(self.client.get(reverse("admin:accounts_user_stats")), tester.email)

    def test_metabase_link_when_set(self):
        self.assertNotContains(self.client.get(reverse("admin:accounts_user_stats")), "Open Metabase")
        with self.settings(METABASE_URL="https://stats.example.fi"):
            self.assertContains(self.client.get(reverse("admin:accounts_user_stats")), 'href="https://stats.example.fi"')

    def test_analytics_views_leave_out_test_data_and_personal_details(self):
        from django.db import connection
        from home.tests import make_ride
        from rides.admin import test_user
        make_ride(test_user())
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM analytics.users")
            self.assertEqual(cursor.fetchone()[0], User.objects.count() - 1)
            cursor.execute("SELECT count(*) FROM analytics.rides")
            self.assertEqual(cursor.fetchone()[0], 1)
            cursor.execute("SELECT * FROM analytics.users LIMIT 0")
            columns = {column.name for column in cursor.description}
        self.assertFalse(columns & {"email", "first_name", "last_name", "phone", "password"})

    def test_sorting_and_unknown_sorts(self):
        for sort in ("rides_posted", "-requests_made", "password", ""):
            self.assertEqual(self.client.get(reverse("admin:accounts_user_stats"), {"sort": sort}).status_code, 200, sort)

    def test_only_for_admins_who_can_view_users(self):
        staff = make_user("Sam", "Staff", is_staff=True)
        log_in_to_admin(self.client, staff)
        self.assertEqual(self.client.get(reverse("admin:accounts_user_stats")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:accounts_user_stats_csv")).status_code, 403)
        self.client.force_login(self.driver)
        self.assertRedirects(self.client.get(reverse("admin:accounts_user_stats")),
                             f"{reverse('admin:login')}?next={reverse('admin:accounts_user_stats')}",
                             fetch_redirect_response=False)

    def test_activity_log_numbers(self):
        from activity.models import Event, Kind
        from accounts.stats import StatsFilterForm, UserStats
        now = timezone.now()
        User.objects.filter(pk=self.passenger.pk).update(date_joined=now - timedelta(days=70))
        self.passenger.refresh_from_db()
        for days_ago in (65, 40, 1):
            Event.objects.create(user=self.passenger, kind=Kind.ACTIVE, data={"device": "mobile"},
                                 created_at=now - timedelta(days=days_ago))
        Event.objects.create(user=self.passenger, kind=Kind.SEARCHED, data={"results": 0, "destination_campus": "Lahti Mukkula campus"})
        Event.objects.create(user=self.passenger, kind=Kind.SEARCHED, data={"results": 3})
        Event.objects.create(user=self.driver, kind=Kind.REQUEST_DECLINED, data={"hours": 2})
        Event.objects.create(user=None, kind=Kind.ACCOUNT_DELETED, data={"domain": "lut.fi", "days": 12, "rides": 0, "requests": 0})
        # The log starts with the passenger's sign-up
        Event.objects.create(user=self.passenger, kind=Kind.SIGNED_UP, created_at=now - timedelta(days=70))

        stats = UserStats(StatsFilterForm())
        tiles = {str(label): (value, str(note)) for label, value, note in stats.tiles()}
        self.assertEqual(tiles["Searches"][0], 2)
        self.assertIn("50 %", tiles["Searches"][1])
        self.assertEqual(tiles["Searchers who asked to join"][0], "100 %")
        self.assertEqual(tiles["Have shared a ride"][0], f"{round(100 * 2 / 3)} %")
        self.assertEqual(tiles["Accounts deleted"][0], 1)
        charts = {chart["id"]: chart for chart in stats.charts()}
        self.assertEqual(charts["campuses"]["series"][0]["data"][1], 1)
        self.assertEqual(charts["devices"]["series"][0]["data"], [3, 0])
        self.assertEqual(charts["called_off"]["series"][0]["data"][2], 1)
        # Joined 70 days ago: active in its 2nd month (days 30–59), not its 3rd (60–89 has not ended)
        # (The others joined this month, and have no months to show yet)
        [(_month, users, cells), (_older, passengers, passenger_cells)] = stats.retention()
        self.assertEqual((users, cells), (2, [""] * 5))
        self.assertEqual((passengers, passenger_cells[:3]), (1, ["100 %", "", ""]))

        rows = self.csv_rows()
        self.assertEqual((rows["jamie.saarinen@lab.fi"]["active_days"], rows["jamie.saarinen@lab.fi"]["searches"]), ("3", "2"))
        page = self.client.get(reverse("admin:accounts_user_stats"))
        for chart in ("active", "searches", "funnel", "campuses", "hours", "features"):
            self.assertContains(page, f'data-chart="{chart}"')
        self.assertContains(page, "Retention")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TwoFactorTests(TestCase):
    """Two-step verification (accounts/two_factor.py)."""

    def setUp(self):
        self.user = make_user("Aino", "Mäkinen")

    def app_code(self):
        # A code is accepted once, so each test login can reuse the current one
        device = TOTPDevice.objects.get(user=self.user)
        TOTPDevice.objects.filter(pk=device.pk).update(last_t=-1)
        return str(TOTP(device.bin_key).token()).zfill(6)

    def wait_out(self):
        """As if the wait after a wrong code had passed."""
        TOTPDevice.objects.update(throttling_failure_timestamp=None)

    def turn_on(self):
        self.client.force_login(self.user)
        self.client.get(reverse("two_factor_setup"))
        self.client.post(reverse("two_factor_setup"), {"code": self.app_code()})
        codes = self.client.get(reverse("backup_codes")).context["codes"]
        self.client.logout()
        return codes

    def log_in(self, next=""):
        url = reverse("login") + (f"?next={next}" if next else "")
        return self.client.post(url, {"username": self.user.email, "password": "Passw0rd!x"})

    def test_turning_on(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("account")), reverse("two_factor_setup"))

        page = self.client.get(reverse("two_factor_setup"))
        self.assertContains(page, "otpauth://totp/LUT%20Kyyti%3Aaino%40lut.fi?secret=")
        self.assertContains(page, "<svg")
        # Reloading keeps the QR code already scanned
        self.assertEqual(self.client.get(reverse("two_factor_setup")).context["secret"], page.context["secret"])

        response = self.client.post(reverse("two_factor_setup"), {"code": "000000"})
        self.assertContains(response, "That code is wrong.")
        self.assertFalse(two_factor.enabled(self.user))

        self.wait_out()
        response = self.client.post(reverse("two_factor_setup"), {"code": self.app_code()})
        self.assertRedirects(response, reverse("backup_codes"), fetch_redirect_response=False)
        self.assertTrue(two_factor.enabled(self.user))
        self.assertEqual(len(self.client.get(reverse("backup_codes")).context["codes"]), two_factor.BACKUP_CODES)
        # Shown once
        self.assertRedirects(self.client.get(reverse("backup_codes")), reverse("account"))
        self.assertEqual(mail.outbox[-1].subject, "Two-step verification is on for your LUT Kyyti account")
        self.assertRedirects(self.client.get(reverse("two_factor_setup")), reverse("account"))
        self.assertContains(self.client.get(reverse("account")), "10 backup codes left")

    def test_logging_in_needs_the_code(self):
        self.turn_on()
        self.assertRedirects(self.log_in(), reverse("login_code"))
        # Not logged in yet
        self.assertEqual(self.client.get(reverse("home")).status_code, 302)

        response = self.client.post(reverse("login_code"), {"code": "000000"})
        self.assertContains(response, "That code is wrong.")
        self.wait_out()
        response = self.client.post(reverse("login_code"), {"code": self.app_code()})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_where_the_user_was_going_is_kept(self):
        self.turn_on()
        self.log_in(next=reverse("my_rides"))
        response = self.client.post(reverse("login_code"), {"code": self.app_code()})
        self.assertRedirects(response, reverse("my_rides"), fetch_redirect_response=False)

    def test_backup_codes_work_once(self):
        code = self.turn_on()[0]
        self.log_in()
        self.assertContains(self.client.get(reverse("login_code"), {"backup": "1"}), "Backup code")
        response = self.client.post(reverse("login_code") + "?backup=1", {"code": f" {code.upper()} "})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertEqual(two_factor.backup_codes_left(self.user), two_factor.BACKUP_CODES - 1)

        self.client.logout()
        self.log_in()
        response = self.client.post(reverse("login_code") + "?backup=1", {"code": code})
        self.assertContains(response, "wrong or has already been used")

    def test_wrong_codes_make_the_user_wait(self):
        self.turn_on()
        self.log_in()
        self.client.post(reverse("login_code"), {"code": "000000"})
        response = self.client.post(reverse("login_code"), {"code": self.app_code()})
        self.assertContains(response, "Too many wrong codes.")
        self.assertEqual(self.client.get(reverse("home")).status_code, 302)

    def test_the_code_page_needs_the_password_first(self):
        self.assertRedirects(self.client.get(reverse("login_code")), reverse("login"))
        self.turn_on()
        self.log_in()
        session = self.client.session
        session[two_factor.SESSION_KEY]["at"] -= two_factor.LOGIN_TIMEOUT + 1
        session.save()
        self.assertRedirects(self.client.post(reverse("login_code"), {"code": self.app_code()}), reverse("login"))

        self.log_in()
        self.client.post(reverse("cancel_login_code"))
        self.assertRedirects(self.client.get(reverse("login_code")), reverse("login"))

    def test_turning_off_and_new_backup_codes_need_the_password(self):
        old_codes = self.turn_on()
        self.log_in()
        self.client.post(reverse("login_code"), {"code": self.app_code()})

        response = self.client.post(reverse("account"), {"form": "backup_codes", "backup_codes-password": "wrong"})
        self.assertContains(response, "The password is incorrect.")
        response = self.client.post(reverse("account"), {"form": "backup_codes", "backup_codes-password": "Passw0rd!x"})
        self.assertRedirects(response, reverse("backup_codes"), fetch_redirect_response=False)
        new_codes = self.client.get(reverse("backup_codes")).context["codes"]
        self.assertFalse(set(old_codes) & set(new_codes))

        response = self.client.post(reverse("account"), {"form": "two_factor_off", "two_factor_off-password": "wrong"})
        self.assertTrue(two_factor.enabled(self.user))
        response = self.client.post(reverse("account"), {"form": "two_factor_off", "two_factor_off-password": "Passw0rd!x"})
        self.assertRedirects(response, reverse("account"))
        self.assertFalse(two_factor.enabled(self.user))
        self.assertEqual(two_factor.backup_codes_left(self.user), 0)
        self.assertEqual(mail.outbox[-1].subject, "Two-step verification was turned off for your LUT Kyyti account")

        self.client.logout()
        self.assertRedirects(self.log_in(), reverse("home"), fetch_redirect_response=False)

    def test_the_admin_needs_two_step_verification(self):
        User.objects.filter(pk=self.user.pk).update(is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        admin_login = self.client.get(reverse("admin:index"), follow=True)
        self.assertRedirects(admin_login, reverse("account") + "#two-step")
        self.assertContains(admin_login, "Turn on two-step verification to use the admin.")

        # Logged in before turning it on elsewhere: logs in again, with the code
        self.turn_on()
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin:index"), follow=True)
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('admin:index')}")
        self.assertRedirects(self.log_in(next=reverse("admin:index")), reverse("login_code"))
        response = self.client.post(reverse("login_code"), {"code": self.app_code()})
        self.assertRedirects(response, reverse("admin:index"))
