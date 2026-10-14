from io import BytesIO

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import User
from test_app.models import Ride, RideRequest


def make_user(first, last, **fields):
    # Users have no username, so they are created like the sign up form does
    user = User(email=f"{first.lower()}@lut.fi", first_name=first, last_name=last, **fields)
    user.set_password("Passw0rd!x")
    user.save()
    return user


def make_ride(driver, **fields):
    place = lambda name: {"displayName": name, "location": {"lat": 61.0, "lng": 28.2}}
    fields = {
        "offer": True, "start_json": place("Lappeenranta"), "destination_json": place("Lahti"),
        "leaving_at_date_time": "2099-10-14T07:30", **fields,
    }
    return Ride.objects.create(driver=driver, **fields)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RideRequestTests(TestCase):
    def setUp(self):
        self.driver = make_user("Aino", "Mäkinen", phone="+358401234567", share_phone=True)
        self.passenger = make_user("Jamie", "Saarinen")
        self.ride = make_ride(self.driver, max_passengers=1)
        self.url = reverse("ride_detail", args=[self.ride.pk])

    def request_ride(self, user, message=""):
        self.client.force_login(user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("request_ride", args=[self.ride.pk]), {"message": message})

    def answer(self, ride_request, action):
        self.client.force_login(self.driver)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("answer_request", args=[ride_request.pk]), {"action": action})

    def test_contact_details_are_only_shown_after_acceptance(self):
        self.request_ride(self.passenger, "Could I join from Kouvola?")
        ride_request = RideRequest.objects.get()
        self.assertEqual(ride_request.status, RideRequest.Status.PENDING)

        page = self.client.get(self.url).content.decode()
        self.assertIn("Aino M.", page)
        self.assertNotIn("Mäkinen", page)
        self.assertNotIn(self.driver.email, page)
        self.assertNotIn(self.driver.phone, page)

        # The driver sees the request without the passenger's contact details
        self.client.force_login(self.driver)
        page = self.client.get(self.url).content.decode()
        self.assertIn("Could I join from Kouvola?", page)
        self.assertNotIn(self.passenger.email, page)

        self.answer(ride_request, "accept")
        page = self.client.get(self.url).content.decode()
        self.assertIn(self.passenger.email, page)

        self.client.force_login(self.passenger)
        page = self.client.get(self.url).content.decode()
        self.assertIn("Aino Mäkinen", page)
        self.assertIn(self.driver.email, page)
        self.assertIn(self.driver.phone, page)

    def test_contact_details_follow_sharing_settings(self):
        self.passenger.share_email = False
        self.passenger.save()
        self.request_ride(self.passenger)
        self.answer(RideRequest.objects.get(), "accept")
        page = self.client.get(self.url).content.decode()
        self.assertNotIn(self.passenger.email, page)

    def test_other_passengers_do_not_see_each_other(self):
        self.ride.max_passengers = 2
        self.ride.save()
        other = make_user("Kalle", "Virtanen")
        for user in (self.passenger, other):
            self.request_ride(user)
        for ride_request in RideRequest.objects.all():
            self.answer(ride_request, "accept")

        self.client.force_login(self.passenger)
        page = self.client.get(self.url).content.decode()
        self.assertNotIn("Kalle", page)
        self.assertNotIn(other.email, page)

    def test_emails_are_sent_and_respect_the_setting(self):
        self.request_ride(self.passenger, "Hello")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.driver.email])
        self.assertIn("Hello", mail.outbox[0].body)
        self.assertNotIn(self.passenger.email, mail.outbox[0].body)

        self.passenger.notify_ride_requests = False
        self.passenger.save()
        self.answer(RideRequest.objects.get(), "accept")
        self.assertEqual(len(mail.outbox), 1)

    def test_seats_limit_acceptance(self):
        other = make_user("Kalle", "Virtanen")
        self.request_ride(self.passenger)
        self.request_ride(other)
        first, second = RideRequest.objects.order_by("created_at")
        self.answer(first, "accept")
        self.answer(second, "accept")
        second.refresh_from_db()
        self.assertEqual(second.status, RideRequest.Status.PENDING)

        # A full ride takes no new requests
        third = make_user("Liisa", "Korhonen")
        self.request_ride(third)
        self.assertFalse(RideRequest.objects.filter(passenger=third).exists())

    def test_declined_passenger_cannot_request_again(self):
        self.request_ride(self.passenger)
        self.answer(RideRequest.objects.get(), "decline")
        self.request_ride(self.passenger)
        self.assertEqual(RideRequest.objects.get().status, RideRequest.Status.DECLINED)
        # Withdrawing does not remove the declined request either
        self.client.post(reverse("withdraw_request", args=[self.ride.pk]))
        self.assertTrue(RideRequest.objects.exists())

    def test_withdraw_and_leave(self):
        self.request_ride(self.passenger)
        self.client.post(reverse("withdraw_request", args=[self.ride.pk]))
        self.assertFalse(RideRequest.objects.exists())

        self.request_ride(self.passenger)
        self.answer(RideRequest.objects.get(), "accept")
        mail.outbox.clear()
        self.client.force_login(self.passenger)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("withdraw_request", args=[self.ride.pk]))
        self.assertFalse(RideRequest.objects.exists())
        self.assertEqual(mail.outbox[0].to, [self.driver.email])

    def test_only_the_driver_answers_requests(self):
        self.request_ride(self.passenger)
        ride_request = RideRequest.objects.get()
        response = self.client.post(reverse("answer_request", args=[ride_request.pk]), {"action": "accept"})
        self.assertEqual(response.status_code, 404)

    def test_driver_cannot_request_own_ride(self):
        self.request_ride(self.driver)
        self.assertFalse(RideRequest.objects.exists())

    def test_past_rides_take_no_requests(self):
        self.ride.leaving_at_date_time = "2000-01-01T08:00"
        self.ride.save()
        self.assertEqual(self.request_ride(self.passenger).status_code, 404)

    def test_deleting_a_ride_notifies_passengers(self):
        self.request_ride(self.passenger)
        mail.outbox.clear()
        self.client.force_login(self.driver)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("delete_ride"), {"ride": self.ride.pk})
        self.assertFalse(Ride.objects.exists())
        self.assertEqual(mail.outbox[0].to, [self.passenger.email])


class PageTests(TestCase):
    def setUp(self):
        self.driver = make_user("Aino", "Mäkinen")
        self.passenger = make_user("Jamie", "Saarinen")
        self.ride = make_ride(self.driver, max_passengers=3)
        make_ride(self.driver, leaving_at_date_time="2000-01-01T08:00")
        RideRequest.objects.create(ride=self.ride, passenger=self.passenger)

    def test_home_shows_requests_to_review(self):
        self.client.force_login(self.driver)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Needs your attention")
        self.assertContains(response, "Jamie S.")
        self.assertEqual(len(response.context["my_rides"]), 1)

    def test_home_lists_requested_rides_and_recent_rides(self):
        self.client.force_login(self.passenger)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Needs your attention")
        self.assertContains(response, "Requested")
        self.assertEqual(list(response.context["recent_rides"]), [self.ride])

    def test_my_rides_splits_upcoming_and_past(self):
        self.client.force_login(self.driver)
        response = self.client.get(reverse("my_rides"))
        self.assertEqual(len(response.context["upcoming"]), 1)
        self.assertEqual(len(response.context["past"]), 1)

    def test_search_results_use_display_names(self):
        self.client.force_login(self.passenger)
        response = self.client.post(reverse("search"), {})
        self.assertContains(response, "Aino M.")
        self.assertNotContains(response, "Mäkinen")


def image_file(size=(800, 600)):
    output = BytesIO()
    Image.new("RGB", size, "purple").save(output, "PNG")
    return SimpleUploadedFile("me.png", output.getvalue(), content_type="image/png")


class AccountTests(TestCase):
    def setUp(self):
        self.user = make_user("Jamie", "Saarinen")
        self.other = make_user("Aino", "Mäkinen")
        self.client.force_login(self.user)
        self.url = reverse("account")

    def tearDown(self):
        for user in User.objects.exclude(pfp=""):
            if user.pfp:
                user.pfp.storage.delete(user.pfp.name)

    def test_profile_and_settings_are_saved(self):
        self.client.post(self.url, {
            "form": "profile", "profile-first_name": "Jamie", "profile-last_name": "S",
            "profile-phone": "+358 40 123 4567",
        })
        self.client.post(self.url, {
            "form": "settings", "settings-name_visibility": "full", "settings-share_phone": "on",
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "S")
        self.assertEqual(self.user.phone, "+358401234567")
        self.assertEqual(self.user.name_visibility, "full")
        self.assertTrue(self.user.share_phone)
        self.assertFalse(self.user.share_email)
        self.assertFalse(self.user.notify_ride_requests)

    def test_photo_is_resized_and_follows_visibility(self):
        self.client.post(self.url, {"form": "photo", "photo-photo": image_file()})
        self.user.refresh_from_db()
        self.assertRegex(self.user.pfp.name, r"^private_media/profile_photos/[0-9a-f]{32}\.jpg$")
        with Image.open(self.user.pfp.path) as image:
            self.assertEqual(image.size, (512, 512))

        photo_url = reverse("user_photo", args=[self.user.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(photo_url).status_code, 200)

        self.user.show_photo = False
        self.user.save()
        self.assertEqual(self.client.get(photo_url).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(photo_url).status_code, 200)

        self.client.logout()
        self.assertEqual(self.client.get(photo_url).status_code, 302)

    def test_photos_set_anywhere_are_shrunk_and_renamed(self):
        # As the admin's user forms do
        self.user.pfp = image_file((3000, 2000))
        self.user.save()
        first = self.user.pfp.name
        self.assertRegex(first, r"^private_media/profile_photos/[0-9a-f]{32}\.jpg$")
        with Image.open(self.user.pfp.path) as image:
            self.assertEqual((image.size, image.format), ((512, 512), "JPEG"))

        # Replacing or removing the photo deletes the old file
        self.client.post(self.url, {"form": "photo", "photo-photo": image_file()})
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.pfp.name, first)
        self.assertFalse(self.user.pfp.storage.exists(first))
        second = self.user.pfp.name
        self.client.post(self.url, {"form": "remove_photo"})
        self.user.refresh_from_db()
        self.assertFalse(self.user.pfp)
        self.assertFalse(self.user.pfp.storage.exists(second))

    def test_photo_must_be_an_image(self):
        not_image = SimpleUploadedFile("me.png", b"not an image", content_type="image/png")
        self.client.post(self.url, {"form": "photo", "photo-photo": not_image})
        self.user.refresh_from_db()
        self.assertFalse(self.user.pfp)

    def test_delete_account_needs_password(self):
        make_ride(self.user)
        self.client.post(self.url, {"form": "delete", "delete-password": "wrong"})
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

        response = self.client.post(self.url, {"form": "delete", "delete-password": "Passw0rd!x"})
        self.assertRedirects(response, reverse("landing"), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Ride.objects.exists())
