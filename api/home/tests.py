from io import BytesIO
import json
from unittest import skipUnless
from unittest.mock import patch
import os

from django.conf import settings
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import User
from test_app.models import Ride, RideRequest


def make_user(first, last, **fields):
    # Users have no username, so they are created like the sign up form does
    fields.setdefault("email_confirmed_at", timezone.now())
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
        self.assertNotIn("+358 40 1234567", page)

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
        self.assertIn('href="tel:+358401234567"', page)
        self.assertIn("+358 40 1234567", page)

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


# A photo with an embedded Adobe RGB (1998) colour profile
WIDE_GAMUT_PHOTO = os.path.join(settings.BASE_DIR, "static/images/user_images/Péter_Magyar_MEP_2024.jpg")


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

    def save_phone(self, value):
        response = self.client.post(self.url, {
            "form": "profile", "profile-first_name": "Jamie", "profile-last_name": "Saarinen", "profile-phone": value,
        })
        self.user.refresh_from_db()
        return response

    def test_phone_numbers_are_checked_and_stored_in_one_format(self):
        for value, stored in [
            ("040 123 4567", "+358401234567"),        # Finnish, without a country code
            ("+358 40 123 4567", "+358401234567"),
            ("(040) 123-4567", "+358401234567"),
            ("+46 70 123 45 67", "+46701234567"),     # Swedish
            ("", None),                               # removes the number
        ]:
            with self.subTest(value=value):
                self.save_phone(value)
                self.assertEqual(self.user.phone, stored)

    def test_invalid_phone_numbers_are_refused(self):
        self.save_phone("040 123 4567")
        for value in ["123", "000000", "+358 00 000", "+1 2 3 4 5 6", "phone me", "040 123 4567 8901 2345"]:
            with self.subTest(value=value):
                response = self.save_phone(value)
                self.assertContains(response, "Enter a valid phone number")
                self.assertEqual(self.user.phone, "+358401234567")

    def test_phone_number_is_shown_spaced_out(self):
        self.save_phone("0401234567")
        self.assertContains(self.client.get(self.url), 'value="+358 40 1234567"')

    def test_photo_is_resized_and_follows_visibility(self):
        self.client.post(self.url, {"form": "photo", "photo-photo": image_file()})
        self.user.refresh_from_db()
        self.assertRegex(self.user.pfp.name, r"^private_media/profile_photos/[0-9a-f]{32}\.jpg$")
        with Image.open(self.user.pfp.path) as image:
            self.assertEqual(image.size, (512, 512))

        photo_url = reverse("user_photo", args=[self.user.pk])
        self.client.force_login(self.other)
        response = self.client.get(photo_url)
        self.assertEqual(response.status_code, 200)
        # Cached by the browser only, and not checked again (the URL changes with the photo)
        self.assertEqual(response["Cache-Control"], "private, max-age=31536000, immutable")

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

    def test_photo_size_limit(self):
        # The page refuses large photos before uploading them (see account.html)
        response = self.client.get(self.url)
        self.assertContains(response, 'data-max-size="10485760"')
        self.assertContains(response, 'data-too-large="The photo must be smaller than 10 MB."')
        self.assertContains(response, "<title>Profile & settings | LUT Kyyti</title>", html=False)

        # and the server refuses them too
        with patch("accounts.forms.PHOTO_MAX_UPLOAD", 100):
            response = self.client.post(self.url, {"form": "photo", "photo-photo": image_file()})
        self.assertContains(response, "The photo must be smaller than")
        self.user.refresh_from_db()
        self.assertFalse(self.user.pfp)

    @skipUnless(os.path.exists(WIDE_GAMUT_PHOTO), "needs the sample Adobe RGB photo")
    def test_wide_gamut_photos_keep_their_colours(self):
        with Image.open(WIDE_GAMUT_PHOTO) as sample:
            adobe_rgb = sample.info["icc_profile"]
        # This muted green in Adobe RGB is a vivid (0, 172, 84) in sRGB
        output = BytesIO()
        Image.new("RGB", (600, 600), (90, 170, 90)).save(output, "JPEG", icc_profile=adobe_rgb, quality=100)
        self.user.pfp = SimpleUploadedFile("green.jpg", output.getvalue(), content_type="image/jpeg")
        self.user.save()

        # The saved photo has no profile, so browsers read its values as sRGB
        with Image.open(self.user.pfp.path) as image:
            pixel = image.getpixel((256, 256))
        for channel, value in zip(pixel, (0, 172, 84)):
            self.assertAlmostEqual(channel, value, delta=6)

    def framed_photo(self, **crop):
        """Uploads a 1000 x 500 photo, red on the left half and blue on the right."""
        image = Image.new("RGB", (1000, 500), "red")
        image.paste((0, 0, 255), (500, 0, 1000, 500))
        output = BytesIO()
        image.save(output, "PNG")
        upload = SimpleUploadedFile("me.png", output.getvalue(), content_type="image/png")
        data = {"form": "photo", "photo-photo": upload}
        data.update({f"photo-crop_{key}": value for key, value in crop.items()})
        self.client.post(self.url, data)
        self.user.refresh_from_db()
        with Image.open(self.user.pfp.path) as saved:
            return saved.size, saved.getpixel((10, 256)), saved.getpixel((501, 256))

    def is_blue(self, pixel):
        return pixel[2] > 200 and pixel[0] < 50

    def test_photo_is_cropped_to_the_framed_square(self):
        size, left, right = self.framed_photo(x=500, y=0, size=500)
        self.assertEqual(size, (512, 512))
        self.assertTrue(self.is_blue(left) and self.is_blue(right))

    def test_photo_crop_is_kept_inside_the_photo(self):
        # Larger than the photo and partly outside it: moved and shrunk to fit
        size, left, right = self.framed_photo(x=900, y=-50, size=800)
        self.assertEqual(size, (512, 512))
        self.assertTrue(self.is_blue(left) and self.is_blue(right))

    def test_photo_without_framing_uses_the_middle(self):
        size, left, right = self.framed_photo()
        self.assertEqual(size, (512, 512))
        self.assertFalse(self.is_blue(left))
        self.assertTrue(self.is_blue(right))

    def test_older_photo_files_are_never_deleted(self):
        # Photos from before uploads were stored privately can be files kept
        # in the repository, such as the sample photos
        legacy = "static/images/user_images/test_legacy_photo.jpg"
        path = os.path.join(settings.BASE_DIR, legacy)
        Image.new("RGB", (10, 10)).save(path)
        self.addCleanup(os.remove, path)
        User.objects.filter(pk=self.user.pk).update(pfp=legacy)

        self.client.post(self.url, {"form": "photo", "photo-photo": image_file()})
        self.client.post(self.url, {"form": "remove_photo"})
        self.assertTrue(os.path.exists(path))

        User.objects.filter(pk=self.user.pk).update(pfp=legacy)
        self.client.post(self.url, {"form": "delete", "delete-password": "Passw0rd!x"})
        self.assertTrue(os.path.exists(path))

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


@patch("home.views.build_route", return_value=None)
class AddRideScheduleTests(TestCase):
    """The add ride page's date and time checks (RideForm.clean)."""

    def setUp(self):
        self.client.force_login(make_user("Aino", "Mäkinen"))
        place = lambda name: json.dumps({"displayName": name, "location": {"lat": 61.0, "lng": 28.2}})
        self.base = {"offer": "on", "start_json": place("Lappeenranta"), "destination_json": place("Lahti")}

    def post(self, **schedule):
        return self.client.post(reverse("add"), {**self.base, **schedule})

    def assert_error(self, response, message):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, message)
        self.assertFalse(Ride.objects.exists())

    # One-time rides

    def test_one_time_one_way(self, _route):
        self.post(one_time="oneTime", one_way="oneWay", leaving_at_date_time="2099-10-14T07:30",
                  returning_at_date_time="2099-10-14T16:00", monday_check="on", monday_leaving_at_time="08:00")
        ride = Ride.objects.get()
        self.assertTrue(ride.one_time and ride.one_way)
        self.assertEqual(ride.leaving_at_date_time, "2099-10-14T07:30")
        # Values for other kinds of rides are not kept
        self.assertEqual(ride.returning_at_date_time, "")
        self.assertFalse(ride.monday_check)
        self.assertEqual(ride.monday_leaving_at_time, "")

    def test_one_time_needs_a_departure(self, _route):
        self.assert_error(self.post(one_time="oneTime", one_way="oneWay"), "Enter the date and time the ride leaves.")
        self.assert_error(self.post(one_time="oneTime", one_way="oneWay", leaving_at_date_time="soon"),
                          "Enter the date and time the ride leaves.")

    def test_one_time_cannot_leave_in_the_past(self, _route):
        self.assert_error(self.post(one_time="oneTime", one_way="oneWay", leaving_at_date_time="2000-01-01T08:00"),
                          "The ride cannot leave in the past.")

    def test_one_time_return(self, _route):
        self.assert_error(self.post(one_time="oneTime", one_way="twoWay", leaving_at_date_time="2099-10-14T07:30"),
                          "Enter the date and time of the return journey.")
        self.assert_error(self.post(one_time="oneTime", one_way="twoWay", leaving_at_date_time="2099-10-14T07:30",
                                    returning_at_date_time="2099-10-14T07:30"),
                          "The return journey must be after the departure.")
        self.post(one_time="oneTime", one_way="twoWay", leaving_at_date_time="2099-10-14T07:30",
                  returning_at_date_time="2099-10-14T16:00")
        ride = Ride.objects.get()
        self.assertFalse(ride.one_way)
        self.assertEqual(ride.returning_at_date_time, "2099-10-14T16:00")

    # Recurring rides

    def test_recurring_one_way(self, _route):
        self.post(one_time="recurring", one_way="oneWay", leaving_at_date_time="2099-10-14T07:30",
                  monday_check="on", monday_leaving_at_time="07:30", monday_returning_at_time="16:00",
                  tuesday_leaving_at_time="09:00")
        ride = Ride.objects.get()
        self.assertFalse(ride.one_time)
        self.assertTrue(ride.monday_check)
        self.assertEqual(ride.monday_leaving_at_time, "07:30")
        # Values for other kinds of rides, and for days not chosen, are not kept
        self.assertEqual(ride.monday_returning_at_time, "")
        self.assertEqual(ride.tuesday_leaving_at_time, "")
        self.assertEqual(ride.leaving_at_date_time, "")

    def test_recurring_needs_a_day(self, _route):
        self.assert_error(self.post(one_time="recurring", one_way="oneWay", leaving_at_date_time="2099-10-14T07:30"),
                          "Choose at least one day for a recurring ride.")

    def test_recurring_days_need_a_departure_time(self, _route):
        self.assert_error(self.post(one_time="recurring", one_way="oneWay", monday_check="on", monday_leaving_at_time="07:30",
                                    wednesday_check="on"),
                          "Enter the time the ride leaves on Wednesday.")

    def test_recurring_return(self, _route):
        self.assert_error(self.post(one_time="recurring", one_way="twoWay", friday_check="on", friday_leaving_at_time="07:30"),
                          "Enter the time of the return journey on Friday.")
        self.assert_error(self.post(one_time="recurring", one_way="twoWay", friday_check="on", friday_leaving_at_time="16:00",
                                    friday_returning_at_time="07:30"),
                          "The return journey on Friday must be after the departure.")
        self.post(one_time="recurring", one_way="twoWay", friday_check="on", friday_leaving_at_time="07:30",
                  friday_returning_at_time="16:00")
        self.assertEqual(Ride.objects.get().friday_returning_at_time, "16:00")

    def test_kind_of_ride_must_be_chosen(self, _route):
        self.assert_error(self.post(one_way="oneWay", leaving_at_date_time="2099-10-14T07:30"),
                          "Choose whether the ride is one-time or recurring.")
        self.assert_error(self.post(one_time="oneTime", leaving_at_date_time="2099-10-14T07:30"),
                          "Choose whether the ride is one-way or has a return journey.")

    def test_schedule_is_kept_after_an_error(self, _route):
        response = self.post(one_time="recurring", one_way="twoWay", monday_check="on", monday_leaving_at_time="07:30",
                             note="Room for luggage")
        self.assertContains(response, 'value="recurring" checked')
        self.assertContains(response, 'value="twoWay" checked')
        self.assertContains(response, 'id="id_monday_check" name="monday_check" type="checkbox" class="checkbox" checked')
        self.assertContains(response, 'value="07:30"')
        self.assertContains(response, "Room for luggage")
