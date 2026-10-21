import random
import uuid
from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import LineString, Point
from django.db import transaction
from django.template.response import TemplateResponse
from django.utils import timezone

from home.campuses import CAMPUSES
from .models import Ride, RideRequest, Via
from .routes import ROUTE_SRID
from .test_places import PLACES
from .transport import TRANSPORT_OPTIONS

class ViaInline(admin.TabularInline):
    model = Via
    extra = 0


class RideRequestInline(admin.TabularInline):
    model = RideRequest
    extra = 0


# Rides made by the "Generate random test rides" action have this key set in
# their start_json, so that "Delete random test rides" deletes only them
TEST_RIDE_KEY = "test_ride"

# The driver of the test rides, made the first time test rides are generated
TEST_USER_EMAIL = "test.user@example.com"

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

TRANSPORT_FIELDS = [option.field for option in TRANSPORT_OPTIONS]

NOTES = [
    "",
    "",
    "Room for a bike in the boot",
    "I can pick you up on the way",
    "No pets please",
    "Leaving a bit early if everyone is on time",
    "Train tickets bought in advance, join me!",
    "Happy to share the taxi fare",
]


PRICES = ["", "", "", "Free", "€5 per passenger", "€10 per passenger", "€15 per passenger", "Split the fuel costs"]


class GenerateRidesForm(forms.Form):
    count = forms.IntegerField(label="Number of rides", initial=100, min_value=1, max_value=10000)


def test_user():
    user, created = get_user_model().objects.get_or_create(
        email=TEST_USER_EMAIL,
        defaults={"username": "testuser", "first_name": "Test", "last_name": "User"},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def place(name, postcode, lat, lng):
    """A place from test_places.PLACES in the Places API format."""
    return {
        "id": f"test-{uuid.uuid4().hex}",
        "displayName": name,
        "formattedAddress": f"{postcode} {name}, Finland",
        "location": {"lat": lat, "lng": lng},
    }


def point(place):
    return Point(place["location"]["lng"], place["location"]["lat"], srid=4326)


def random_times():
    """A leaving time and a later returning time on the same day."""
    leaving = random.randint(6 * 4, 18 * 4) * 15
    returning = random.randint(leaving // 15 + 4, 22 * 4) * 15
    return f"{leaving // 60:02d}:{leaving % 60:02d}", f"{returning // 60:02d}:{returning % 60:02d}"


def random_ride(driver):
    """A random ride from a real place in Finland, and the places it stops at on the way."""
    start, *others = [place(*p) for p in random.sample(PLACES, 3)]
    if random.random() < 0.75:
        destination = dict(random.choice(CAMPUSES)["place"])
    else:
        destination = others.pop()
    vias = others[:random.choices([0, 1, 2], weights=[70, 20, 10])[0]]
    start[TEST_RIDE_KEY] = True

    ride = Ride(
        driver=driver,
        start=start["formattedAddress"],
        start_json=start,
        start_location=point(start),
        destination=destination["formattedAddress"],
        destination_json=destination,
        destination_location=point(destination),
        one_time=random.random() < 0.6,
        one_way=random.random() < 0.5,
        note=random.choice(NOTES),
        price=random.choice(PRICES),
    )
    # Straight lines instead of the driving route, so no Routes API requests are made
    points = [point(p) for p in [start, *vias, destination]]
    ride.route = LineString(points, srid=4326).transform(ROUTE_SRID, clone=True)

    # Mostly one way of travelling, but some rides have several or all of them
    count = random.choices(range(1, len(TRANSPORT_FIELDS) + 1), weights=[40, 25, 15, 8, 4, 8])[0]
    for field in random.sample(TRANSPORT_FIELDS, count):
        setattr(ride, field, True)
    if ride.offer:
        ride.max_passengers = random.choice([None, 1, 2, 3, 4, 5, 6])
    if ride.other:
        ride.other_field = random.choice(["Bike", "Scooter", "Ferry", "Walking"])

    if ride.one_time:
        day = timezone.localtime() + timedelta(days=random.randint(-7, 30))
        leaving, returning = random_times()
        ride.leaving_at_date_time = f"{day:%Y-%m-%d}T{leaving}"
        if not ride.one_way:
            day += timedelta(days=random.choice([0, 0, 1, 2, 3]))
            ride.returning_at_date_time = f"{day:%Y-%m-%d}T{returning}"
    else:
        for day in random.sample(WEEKDAYS, random.randint(1, 7)):
            leaving, returning = random_times()
            setattr(ride, f"{day}_check", True)
            setattr(ride, f"{day}_leaving_at_time", leaving)
            if not ride.one_way:
                setattr(ride, f"{day}_returning_at_time", returning)
    return ride, vias


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    inlines = [ViaInline, RideRequestInline]
    actions = ["generate_test_rides", "delete_test_rides"]

    # Actions that do not act on the selected rides, so they can be run with none selected
    unselected_actions = {"generate_test_rides", "delete_test_rides"}

    def changelist_view(self, request, extra_context=None):
        if request.method == "POST" and request.POST.get("action") in self.unselected_actions:
            post = request.POST.copy()
            if not post.getlist(helpers.ACTION_CHECKBOX_NAME):
                post.setlist(helpers.ACTION_CHECKBOX_NAME, ["0"])
            post["select_across"] = "1"
            request.POST = post
        return super().changelist_view(request, extra_context)

    @admin.action(description="Generate random test rides")
    def generate_test_rides(self, request, queryset):
        form = GenerateRidesForm(request.POST if "apply" in request.POST else None)
        if not form.is_valid():
            return TemplateResponse(request, "admin/rides/ride/generate_test_rides.html", {
                **self.admin_site.each_context(request),
                "title": "Generate random test rides",
                "opts": self.model._meta,
                "form": form,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            })

        count = form.cleaned_data["count"]
        driver = test_user()
        rides = [random_ride(driver) for _ in range(count)]
        with transaction.atomic():
            Ride.objects.bulk_create([ride for ride, _vias in rides], batch_size=500)
            Via.objects.bulk_create([
                Via(ride=ride, order=order, via_json=via, location=point(via))
                for ride, vias in rides
                for order, via in enumerate(vias)
            ], batch_size=500)
        self.message_user(request, f"Generated {count} random test rides for {driver.email}.", messages.SUCCESS)
        return None

    @admin.action(description="Delete random test rides")
    def delete_test_rides(self, request, queryset):
        deleted = Ride.objects.filter(**{f"start_json__{TEST_RIDE_KEY}": True}).delete()[1].get(Ride._meta.label, 0)
        self.message_user(request, f"Deleted {deleted} random test rides.", messages.SUCCESS)
