import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from django.conf import settings
from django.core.management import call_command
from py_vapid import Vapid01
from py_vapid.utils import b64urlencode
from pywebpush import WebPushException

from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from home.tests import make_ride, make_user
from rides.models import Ride, RideRequest
from . import services
from .models import ESSENTIAL, Kind, Notification, PushSubscription


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationEventTests(TestCase):
    """Each ride event notifies the right people, in the app and by email."""

    def setUp(self):
        self.driver = make_user("Aino", "Mäkinen")
        self.passenger = make_user("Jamie", "Saarinen")
        self.ride = make_ride(self.driver, max_passengers=3)

    def as_user(self, user, url, data=None):
        self.client.force_login(user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, data or {})

    def request(self, user=None, message=""):
        self.as_user(user or self.passenger, reverse("request_ride", args=[self.ride.pk]), {"message": message})
        return RideRequest.objects.get(passenger=user or self.passenger)

    def answer(self, ride_request, action):
        self.as_user(self.driver, reverse("answer_request", args=[ride_request.pk]), {"action": action})

    def latest(self, user):
        return user.notifications.first()

    def test_request_received(self):
        self.request(message="Room for a bag?")
        notification = self.latest(self.driver)
        self.assertEqual((notification.kind, notification.ride), (Kind.REQUEST_RECEIVED, self.ride))
        self.assertEqual(notification.message(), "Jamie S. would like to join your ride Lappeenranta → Lahti.")
        self.assertIn("Room for a bag?", mail.outbox[-1].body)

    def test_withdrawing_and_leaving(self):
        self.request()
        self.as_user(self.passenger, reverse("withdraw_request", args=[self.ride.pk]))
        self.assertEqual(self.latest(self.driver).kind, Kind.REQUEST_WITHDRAWN)

        self.answer(self.request(), "accept")
        self.as_user(self.passenger, reverse("withdraw_request", args=[self.ride.pk]))
        notification = self.latest(self.driver)
        self.assertEqual(notification.kind, Kind.PASSENGER_LEFT)
        # Ride partners see full names
        self.assertIn("Jamie Saarinen", notification.message())

    def test_answers(self):
        ride_request = self.request()
        self.answer(ride_request, "accept")
        self.assertEqual(self.latest(self.passenger).kind, Kind.REQUEST_ACCEPTED)
        self.assertIn("Aino Mäkinen accepted", self.latest(self.passenger).message())

        # Removing an accepted passenger is not a "decline"
        self.answer(ride_request, "decline")
        self.assertEqual(self.latest(self.passenger).kind, Kind.PASSENGER_REMOVED)

        other = make_user("Kalle", "Virtanen")
        self.answer(self.request(other), "decline")
        self.assertEqual(self.latest(other).kind, Kind.REQUEST_DECLINED)
        self.assertIn("Aino M. declined", self.latest(other).message())

    def test_ride_changes_reach_everyone_waiting_or_joined(self):
        joined, waiting, declined = make_user("Kalle", "X"), make_user("Liisa", "X"), make_user("Pekka", "X")
        for user, status in ((joined, "accepted"), (waiting, "pending"), (declined, "declined")):
            RideRequest.objects.create(ride=self.ride, passenger=user, status=status)

        with self.captureOnCommitCallbacks(execute=True):
            services.ride_updated(RequestFactory().get("/"), self.ride)
        self.assertEqual(self.latest(joined).kind, Kind.RIDE_UPDATED)
        self.assertEqual(self.latest(waiting).kind, Kind.RIDE_UPDATED)
        self.assertIsNone(self.latest(declined))

        self.as_user(self.driver, reverse("delete_ride"), {"ride": self.ride.pk})
        cancelled = self.latest(joined)
        self.assertEqual(cancelled.kind, Kind.RIDE_CANCELLED)
        # Kept after the ride is gone, with its route
        self.assertFalse(Ride.objects.exists())
        cancelled.refresh_from_db()
        self.assertIsNone(cancelled.ride)
        self.assertIsNone(cancelled.url())
        self.assertIn("Lappeenranta → Lahti", cancelled.message())

    def test_deleting_an_account_tells_the_drivers(self):
        other_driver = make_user("Kalle", "Virtanen")
        other_ride = make_ride(other_driver)
        RideRequest.objects.create(ride=self.ride, passenger=self.passenger, status="accepted")
        RideRequest.objects.create(ride=other_ride, passenger=self.passenger, status="pending")
        self.as_user(self.passenger, reverse("account"), {"form": "delete", "delete-password": "Passw0rd!x"})
        self.assertEqual(self.latest(self.driver).kind, Kind.PASSENGER_LEFT)
        self.assertEqual(self.latest(other_driver).kind, Kind.REQUEST_WITHDRAWN)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailPreferenceTests(TestCase):
    def test_essential_only(self):
        user = make_user("Jamie", "Saarinen", email_notifications="essential")
        self.assertTrue(user.wants_email(Kind.RIDE_CANCELLED))
        self.assertFalse(user.wants_email(Kind.REQUEST_RECEIVED))
        self.assertFalse(user.wants_email(Kind.REQUEST_WITHDRAWN))
        everything = make_user("Aino", "Mäkinen")
        self.assertTrue(all(everything.wants_email(kind) for kind in Kind))

    def test_the_app_shows_every_notification_whatever_is_emailed(self):
        driver = make_user("Aino", "Mäkinen", email_notifications="essential")
        ride = make_ride(driver)
        self.client.force_login(make_user("Jamie", "Saarinen"))
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("request_ride", args=[ride.pk]))
        self.assertEqual(driver.notifications.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_essential_kinds(self):
        self.assertEqual(
            {kind.value for kind in Kind if kind not in ESSENTIAL},
            {"request_received", "request_withdrawn", "group_join_requested"},
        )


class NotificationViewTests(TestCase):
    def setUp(self):
        self.user = make_user("Aino", "Mäkinen")
        self.ride = make_ride(self.user)
        self.notification = Notification.objects.create(
            recipient=self.user, kind=Kind.REQUEST_RECEIVED, ride=self.ride,
            data={"name": "Jamie S.", "route": "Lappeenranta → Lahti"},
        )
        self.client.force_login(self.user)

    def test_bell_shows_the_unread_count(self):
        page = self.client.get(reverse("home")).content.decode()
        self.assertIn("data-unread-badge>1</span>", page)

    def test_menu_and_list(self):
        Notification.objects.create(recipient=make_user("Kalle", "X"), kind=Kind.RIDE_CANCELLED, data={"name": "Someone else"})
        for url in (reverse("notifications_menu"), reverse("notifications")):
            response = self.client.get(url)
            self.assertContains(response, "Jamie S. would like to join your ride")
            self.assertNotContains(response, "Someone else")
            self.assertContains(response, "Mark all as read")

    def test_opening_marks_read_and_goes_to_the_ride(self):
        response = self.client.get(reverse("open_notification", args=[self.notification.pk]))
        self.assertRedirects(response, reverse("ride_detail", args=[self.ride.pk]), fetch_redirect_response=False)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

        self.client.force_login(make_user("Kalle", "X"))
        self.assertEqual(self.client.get(reverse("open_notification", args=[self.notification.pk])).status_code, 404)

    def test_seeing_the_ride_marks_its_notifications_read(self):
        self.client.get(reverse("ride_detail", args=[self.ride.pk]))
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_mark_all_read(self):
        response = self.client.post(reverse("notifications_mark_all_read"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.json(), {"unread": 0})
        self.assertFalse(self.user.notifications.filter(read_at__isnull=True).exists())

    def test_poll_returns_what_is_new(self):
        before = (self.notification.created_at - timedelta(seconds=1)).isoformat()
        data = self.client.get(reverse("notifications_poll"), {"since": before}).json()
        self.assertEqual(data["unread"], 1)
        self.assertEqual([n["id"] for n in data["notifications"]], [str(self.notification.pk)])
        self.assertEqual(data["notifications"][0]["url"], reverse("open_notification", args=[self.notification.pk]))

        data = self.client.get(reverse("notifications_poll"), {"since": data["now"]}).json()
        self.assertEqual(data["notifications"], [])
        # Without a time, only the count
        self.assertEqual(self.client.get(reverse("notifications_poll")).json()["notifications"], [])

    def test_logged_out(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("notifications_poll")).status_code, 302)


PUSH_KEYS = {"VAPID_PUBLIC_KEY": "BPublicKeyForTests", "VAPID_PRIVATE_KEY": "private-key-for-tests"}
SUBSCRIPTION = {
    "endpoint": "https://push.example.com/send/abc123",
    "keys": {"p256dh": "BKeyP256dh", "auth": "authsecret"},
}


@override_settings(**PUSH_KEYS)
class PushSubscriptionTests(TestCase):
    def setUp(self):
        self.user = make_user("Aino", "Mäkinen")
        self.client.force_login(self.user)

    def subscribe(self, data=SUBSCRIPTION):
        return self.client.post(reverse("push_subscribe"), json.dumps(data), content_type="application/json")

    def test_subscribing_and_unsubscribing(self):
        self.assertEqual(self.subscribe().status_code, 200)
        subscription = self.user.push_subscriptions.get()
        self.assertEqual(subscription.as_subscription_info(), SUBSCRIPTION)

        # Sending it again (on every visit) keeps one
        self.subscribe()
        self.assertEqual(PushSubscription.objects.count(), 1)

        self.client.post(reverse("push_unsubscribe"), json.dumps({"endpoint": SUBSCRIPTION["endpoint"]}), content_type="application/json")
        self.assertFalse(PushSubscription.objects.exists())

    def test_a_device_moves_to_the_account_that_turned_it_on(self):
        self.subscribe()
        other = make_user("Jamie", "Saarinen")
        self.client.force_login(other)
        self.subscribe()
        self.assertEqual(PushSubscription.objects.get().user, other)

    def test_bad_subscriptions_are_refused(self):
        for data in ({}, {"endpoint": "http://not-https.example.com"}, {"endpoint": "https://x", "keys": {}}):
            self.assertEqual(self.subscribe(data).status_code, 400)
        self.assertEqual(self.client.post(reverse("push_subscribe"), "not json", content_type="application/json").status_code, 400)
        self.client.logout()
        self.assertEqual(self.subscribe().status_code, 302)

    def test_pages_get_the_public_key_and_the_switch(self):
        page = self.client.get(reverse("account")).content.decode()
        self.assertIn('data-public-key="BPublicKeyForTests"', page)
        self.assertIn('id="push-settings"', page)
        self.assertNotIn("private-key-for-tests", page)

    @override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY="")
    def test_without_keys_push_is_off(self):
        page = self.client.get(reverse("account")).content.decode()
        self.assertNotIn("push-config", page)
        self.assertNotIn('id="push-settings"', page)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", **PUSH_KEYS)
class PushDeliveryTests(TestCase):
    def setUp(self):
        self.driver = make_user("Aino", "Mäkinen")
        self.ride = make_ride(self.driver)
        self.phone = PushSubscription.objects.create(user=self.driver, endpoint="https://push.example.com/1", p256dh="k", auth="a")
        self.laptop = PushSubscription.objects.create(user=self.driver, endpoint="https://push.example.com/2", p256dh="k", auth="a")

    def notify(self):
        with self.captureOnCommitCallbacks(execute=True):
            services.send(RequestFactory().get("/"), self.driver, Kind.REQUEST_RECEIVED, self.ride, name="Jamie S.")

    @patch("notifications.push.webpush")
    def test_each_device_gets_it(self, webpush):
        self.notify()
        self.assertEqual(webpush.call_count, 2)
        call = webpush.call_args.kwargs
        payload = json.loads(call["data"])
        self.assertEqual(payload["title"], "New ride request")
        self.assertIn("Jamie S. would like to join your ride", payload["message"])
        self.assertTrue(payload["url"].startswith("/app/notifications/"))
        self.assertIn("android-chrome-192x192.png", payload["icon"])
        self.assertEqual(call["vapid_private_key"], "private-key-for-tests")
        self.assertTrue(call["vapid_claims"]["sub"].startswith("mailto:"))
        self.phone.refresh_from_db()
        self.assertIsNotNone(self.phone.last_used_at)

    @patch("notifications.push.webpush")
    def test_gone_devices_are_forgotten(self, webpush):
        gone = WebPushException("Gone", response=type("Response", (), {"status_code": 410})())
        webpush.side_effect = [gone, None]
        self.notify()
        self.assertEqual(list(PushSubscription.objects.all()), [self.laptop])

    @patch("notifications.push.webpush", side_effect=WebPushException("Server error", response=type("Response", (), {"status_code": 500})()))
    def test_failures_do_not_stop_other_channels(self, webpush):
        self.notify()
        self.assertEqual(PushSubscription.objects.count(), 2)
        # The email was still sent, and the notification saved
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.driver.notifications.count(), 1)

    @override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY="")
    @patch("notifications.push.webpush")
    def test_without_keys_nothing_is_pushed(self, webpush):
        self.notify()
        webpush.assert_not_called()


class PushKeyCommandTests(TestCase):
    def test_keys_work_with_pywebpush(self):
        out = StringIO()
        call_command("generate_vapid_keys", stdout=out)
        lines = dict(line.split("=", 1) for line in out.getvalue().splitlines() if "=" in line and not line.startswith("#"))
        vapid = Vapid01.from_string(lines["VAPID_PRIVATE_KEY"])
        public = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.assertEqual(b64urlencode(public), lines["VAPID_PUBLIC_KEY"])


class FasterPagesTests(TestCase):
    """Turbo Drive and what pages need for it (static/js/turbo-setup.js)."""

    def setUp(self):
        self.user = make_user("Aino", "Mäkinen")
        self.client.force_login(self.user)
        self.ride = make_ride(self.user)

    def test_layout_loads_turbo_and_no_jquery(self):
        page = self.client.get(reverse("home")).content.decode()
        self.assertIn("turbo-8.0.23.umd.min.js", page)
        self.assertIn('<meta name="turbo-root" content="/app">', page)
        self.assertIn(f"turbo-setup.js?v={settings.STATIC_VERSION}", page)
        self.assertNotIn("jquery", page.lower())
        self.assertNotIn("js.cookie", page)
        # Loaded once from <head>, not again with every page shown
        body = page[page.index("<body"):]
        self.assertNotIn("notifications.js", body)
        self.assertNotIn("push.js", body)

    def test_pages_with_widgets_are_not_kept_for_going_back(self):
        for url in (reverse("search"), reverse("add"), reverse("edit_ride", args=[self.ride.pk]), reverse("account")):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), '<meta name="turbo-cache-control" content="no-cache">')
        self.assertNotContains(self.client.get(reverse("home")), "turbo-cache-control")

    def test_a_ride_loaded_early_marks_its_notifications_read_when_shown(self):
        notification = Notification.objects.create(recipient=self.user, kind=Kind.RIDE_UPDATED, ride=self.ride, data={"name": "X"})
        url = reverse("ride_detail", args=[self.ride.pk])

        # Loaded early (a link hovered or touched): not read yet
        response = self.client.get(url, HTTP_X_SEC_PURPOSE="prefetch")
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)
        self.assertContains(response, f'data.append("ride", "{self.ride.pk}")')

        # The page, once shown, marks them read
        self.client.post(reverse("notifications_mark_all_read"), {"ride": str(self.ride.pk)}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_marking_one_rides_notifications_read(self):
        other_ride = make_ride(self.user)
        mine = Notification.objects.create(recipient=self.user, kind=Kind.RIDE_UPDATED, ride=self.ride, data={})
        other = Notification.objects.create(recipient=self.user, kind=Kind.RIDE_UPDATED, ride=other_ride, data={})
        self.client.post(reverse("notifications_mark_all_read"), {"ride": str(self.ride.pk)}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        mine.refresh_from_db(); other.refresh_from_db()
        self.assertTrue(mine.is_read)
        self.assertFalse(other.is_read)
        self.assertEqual(self.client.post(reverse("notifications_mark_all_read"), {"ride": "nope"}).status_code, 400)

    def test_notification_links_are_not_loaded_early(self):
        Notification.objects.create(recipient=self.user, kind=Kind.RIDE_UPDATED, ride=self.ride, data={"name": "X"})
        self.assertContains(self.client.get(reverse("notifications")), 'data-turbo-prefetch="false"')
