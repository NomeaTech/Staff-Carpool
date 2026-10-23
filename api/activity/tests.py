import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from home.campuses import CAMPUSES
from home.tests import make_ride, make_user, log_in_to_admin
from rides.admin import TEST_RIDE_KEY, test_user
from rides.models import Ride, RideRequest
from .models import Event, Kind


def kinds(user=None):
    events = Event.objects.order_by("created_at")
    return list((events.filter(user=user) if user else events).values_list("kind", flat=True))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RecordingTests(TestCase):
    """What the activity log records (activity/models.py), and what it leaves out."""

    def setUp(self):
        self.driver = make_user("Aino", "Mäkinen")
        self.passenger = make_user("Jamie", "Saarinen")
        self.ride = make_ride(self.driver, max_passengers=2)

    def test_daily_visits_are_recorded_once_a_day(self):
        self.client.force_login(self.passenger)
        mobile = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile/15E148"
        self.client.get(reverse("home"), HTTP_USER_AGENT=mobile)
        self.client.get(reverse("my_rides"))
        visits = Event.objects.filter(user=self.passenger, kind=Kind.ACTIVE)
        self.assertEqual([event.data for event in visits], [{"device": "mobile"}])

        # Another device the same day is the same day
        self.client.session.flush()
        self.client.force_login(self.passenger)
        self.client.get(reverse("home"))
        self.assertEqual(visits.count(), 1)

        # The next day counts again
        visits.update(created_at=timezone.now() - timedelta(days=1))
        session = self.client.session
        session["active_on"] = (timezone.localdate() - timedelta(days=1)).isoformat()
        session.save()
        self.client.get(reverse("home"))
        self.assertEqual(visits.count(), 2)

    def test_admin_pages_are_not_a_visit(self):
        admin = make_user("Ada", "Admin", is_staff=True, is_superuser=True)
        log_in_to_admin(self.client, admin)
        self.client.get(reverse("admin:index"))
        self.assertFalse(Event.objects.filter(kind=Kind.ACTIVE).exists())

    def test_logins_and_logouts(self):
        self.client.post(reverse("login"), {"username": self.passenger.email, "password": "Passw0rd!x"})
        self.client.post(reverse("logout"))
        self.assertEqual([kind for kind in kinds(self.passenger) if kind != Kind.ACTIVE], [Kind.LOGGED_IN, Kind.LOGGED_OUT])

    def test_a_ride_from_request_to_leaving(self):
        self.client.force_login(self.passenger)
        self.client.get(reverse("ride_detail", args=[self.ride.pk]))
        self.client.post(reverse("request_ride", args=[self.ride.pk]), {"message": "Hi, I'm at the main door"})
        request = RideRequest.objects.get()

        self.client.force_login(self.driver)
        self.client.get(reverse("ride_detail", args=[self.ride.pk]))
        self.client.post(reverse("answer_request", args=[request.pk]), {"action": "accept"})

        self.client.force_login(self.passenger)
        self.client.post(reverse("withdraw_request", args=[self.ride.pk]))

        events = Event.objects.exclude(kind__in=[Kind.ACTIVE, Kind.LOGGED_IN]).order_by("created_at")
        self.assertEqual(
            [(e.user, e.kind, e.ride_id) for e in events],
            [
                (self.passenger, Kind.RIDE_VIEWED, self.ride.pk),
                (self.passenger, Kind.REQUEST_SENT, self.ride.pk),
                (self.driver, Kind.RIDE_VIEWED, self.ride.pk),
                (self.driver, Kind.REQUEST_ACCEPTED, self.ride.pk),
                (self.passenger, Kind.PASSENGER_LEFT, self.ride.pk),
            ],
        )
        self.assertEqual(events[0].data, {"role": "other"})
        self.assertEqual(events[1].data, {"message": True, "seats_left": 2})
        self.assertEqual(events[2].data, {"role": "driver"})
        # The message itself is not kept
        self.assertNotIn("main door", json.dumps([e.data for e in events]))

    def test_prefetched_pages_are_not_a_view(self):
        self.client.force_login(self.passenger)
        self.client.get(reverse("ride_detail", args=[self.ride.pk]), HTTP_X_SEC_PURPOSE="prefetch")
        self.assertFalse(Event.objects.filter(kind=Kind.RIDE_VIEWED).exists())

    def test_declines_withdrawals_and_deleted_rides(self):
        request = RideRequest.objects.create(ride=self.ride, passenger=self.passenger)
        self.client.force_login(self.driver)
        self.client.post(reverse("answer_request", args=[request.pk]), {"action": "decline"})
        other = make_user("Sam", "Virtanen")
        RideRequest.objects.create(ride=self.ride, passenger=other, status=RideRequest.Status.ACCEPTED)
        self.client.post(reverse("delete_ride"), {"ride": self.ride.pk})

        self.assertEqual(kinds(self.driver)[-2:], [Kind.REQUEST_DECLINED, Kind.RIDE_DELETED])
        deleted = Event.objects.get(kind=Kind.RIDE_DELETED)
        self.assertEqual((deleted.ride_id, deleted.data["passengers"], deleted.data["upcoming"]), (self.ride.pk, 1, True))
        # Kept, though the ride is gone
        self.assertFalse(Ride.objects.exists())

    def test_searches_keep_what_was_searched_for_but_not_where(self):
        self.client.force_login(self.passenger)
        campus = CAMPUSES[0]["place"]
        home = {"displayName": "Home street 1", "location": {"lat": 61.05, "lng": 28.1}}
        self.client.post(reverse("search"), {
            "start_json": json.dumps(home), "destination_json": json.dumps(campus), "train": "on",
        })
        # Changing the page of results is not a new search
        self.client.post(reverse("search"), {"page": "2"})
        search = Event.objects.get(kind=Kind.SEARCHED)
        self.assertEqual(search.data["destination_campus"], campus["displayName"])
        self.assertIsNone(search.data["start_campus"])
        self.assertEqual((search.data["start"], search.data["date"], search.data["transport"]), (True, False, ["train"]))
        self.assertEqual(search.data["results"], 0)
        self.assertNotIn("Home street", json.dumps(search.data))
        self.assertNotIn("61.05", json.dumps(search.data))

    @patch("home.views.build_route", return_value=None)
    def test_posting_and_editing_rides(self, _build_route):
        self.client.force_login(self.driver)
        place = lambda name: json.dumps({"displayName": name, "location": {"lat": 61.0, "lng": 28.2}})
        leaving = (timezone.localdate() + timedelta(days=3)).isoformat() + "T07:30"
        data = {"offer": "on", "max_passengers": "3", "start_json": place("Lappeenranta"),
                "destination_json": json.dumps(CAMPUSES[1]["place"]), "one_time": "oneTime", "one_way": "oneWay",
                "leaving_at_date_time": leaving}
        self.client.post(reverse("add"), data)
        posted = Event.objects.get(kind=Kind.RIDE_POSTED)
        self.assertEqual(posted.data["transport"], ["offer"])
        self.assertEqual((posted.data["seats"], posted.data["days_ahead"]), (3, 3))
        self.assertEqual(posted.data["destination_campus"], CAMPUSES[1]["place"]["displayName"])

        self.client.post(reverse("edit_ride", args=[posted.ride_id]), {**data, "max_passengers": "2"})
        self.assertEqual(Event.objects.get(kind=Kind.RIDE_EDITED).data, {"places": False})

    def test_profile_and_settings(self):
        self.client.force_login(self.passenger)
        self.client.post(reverse("account"), {
            "form": "settings", "settings-name_visibility": "full", "settings-show_photo": "on",
            "settings-share_email": "on", "settings-email_notifications": "essential",
        })
        settings = Event.objects.get(kind=Kind.SETTINGS_SAVED)
        self.assertEqual(settings.data["changed"], {"name_visibility": "full", "email_notifications": "essential"})

        self.client.post(reverse("account"), {"form": "profile", "profile-first_name": "Jamie",
                                              "profile-last_name": "Saarinen", "profile-phone": "+358401234567"})
        profile = Event.objects.get(kind=Kind.PROFILE_SAVED)
        # Which fields changed, not what they were changed to
        self.assertEqual(profile.data, {"fields": ["phone"]})

    def test_deleted_accounts_are_kept_anonymously(self):
        self.client.force_login(self.passenger)
        self.client.get(reverse("home"))
        RideRequest.objects.create(ride=self.ride, passenger=self.passenger)
        self.client.post(reverse("account"), {"form": "delete", "delete-password": "Passw0rd!x"})

        self.assertFalse(User.objects.filter(pk=self.passenger.pk).exists())
        deleted = Event.objects.get(kind=Kind.ACCOUNT_DELETED)
        self.assertIsNone(deleted.user)
        self.assertEqual(deleted.data, {"domain": "lut.fi", "days": 0, "rides": 0, "requests": 1})
        # The account's earlier events are kept, without it
        self.assertTrue(Event.objects.filter(kind=Kind.ACTIVE, user=None).exists())

    def test_notifications_and_push(self):
        from notifications.models import Notification
        notification = Notification.objects.create(recipient=self.passenger, kind="request_accepted", ride=self.ride)
        self.client.force_login(self.passenger)
        self.client.get(reverse("open_notification", args=[notification.pk]))
        self.assertEqual(Event.objects.get(kind=Kind.NOTIFICATION_OPENED).data["kind"], "request_accepted")

        subscription = {"endpoint": "https://fcm.googleapis.com/fcm/send/1", "keys": {"p256dh": "key", "auth": "auth"}}
        for _ in range(2):
            self.client.post(reverse("push_subscribe"), json.dumps(subscription), content_type="application/json")
        self.client.post(reverse("push_unsubscribe"), json.dumps(subscription), content_type="application/json")
        self.assertEqual([k for k in kinds(self.passenger) if k.startswith("push")], [Kind.PUSH_ON, Kind.PUSH_OFF])

    def test_nothing_about_the_test_user_or_test_rides(self):
        tester = test_user()
        self.client.force_login(tester)
        self.client.get(reverse("home"))
        self.client.get(reverse("ride_detail", args=[self.ride.pk]))

        place = {"displayName": "Imatra", TEST_RIDE_KEY: True, "location": {"lat": 61.2, "lng": 28.8}}
        test_ride = make_ride(self.driver, start_json=place)
        self.client.force_login(self.passenger)
        self.client.get(reverse("ride_detail", args=[test_ride.pk]))
        self.client.post(reverse("request_ride", args=[test_ride.pk]))

        self.assertEqual(kinds(tester), [])
        self.assertFalse(Event.objects.filter(ride_id=test_ride.pk).exists())

    def test_a_failure_to_record_does_not_stop_the_user(self):
        self.client.force_login(self.passenger)
        with patch("activity.events.Event.objects.create", side_effect=RuntimeError), self.assertLogs("activity.events"):
            response = self.client.post(reverse("request_ride", args=[self.ride.pk]))
        self.assertRedirects(response, reverse("ride_detail", args=[self.ride.pk]))
        self.assertTrue(RideRequest.objects.exists())


class AnonymiseTests(TestCase):
    def test_old_events_lose_their_user_and_ride_on_the_first_visit_of_a_day(self):
        user = make_user("Aino", "Mäkinen")
        ride = make_ride(user)
        old = Event.objects.create(user=user, kind=Kind.RIDE_POSTED, ride_id=ride.pk, data={"seats": 3},
                                   created_at=timezone.now() - timedelta(days=40))
        recent = Event.objects.create(user=user, kind=Kind.RIDE_VIEWED, ride_id=ride.pk,
                                      created_at=timezone.now() - timedelta(days=20))
        self.client.force_login(user)
        with self.settings(ACTIVITY_ANONYMISE_DAYS=30):
            self.client.get(reverse("home"))
        old.refresh_from_db()
        recent.refresh_from_db()
        # Kept for the statistics, but no longer anyone's
        self.assertEqual((old.user, old.ride_id, old.kind, old.data), (None, None, Kind.RIDE_POSTED, {"seats": 3}))
        self.assertEqual((recent.user, recent.ride_id), (user, ride.pk))

    def test_anonymised_events_still_count_when_users_are_not_filtered(self):
        from accounts.stats import StatsFilterForm, UserStats
        Event.objects.create(user=None, kind=Kind.SEARCHED, data={"results": 0})
        self.assertEqual(UserStats(StatsFilterForm()).events.count(), 1)
        self.assertEqual(UserStats(StatsFilterForm({"domain": "lut.fi"})).events.count(), 0)
