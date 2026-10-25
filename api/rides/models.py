from django.db import models
from django.contrib.gis.db import models
from django.conf import settings
from django.utils.translation import gettext as _, gettext_lazy
from django.utils import timezone
from itertools import compress
from datetime import datetime
from django.contrib.postgres.fields import ArrayField
from django.db.models import OuterRef
import uuid

from .transport import TRANSPORT_OPTIONS

# A recurring ride's days: the start of their fields' names (monday_check...)
WEEKDAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# The same days, as its schedule names them ("Mondays 07:30")
WEEKDAY_PLURALS = [
    gettext_lazy("Mondays"),
    gettext_lazy("Tuesdays"),
    gettext_lazy("Wednesdays"),
    gettext_lazy("Thursdays"),
    gettext_lazy("Fridays"),
    gettext_lazy("Saturdays"),
    gettext_lazy("Sundays"),
]

class RideQuerySet(models.QuerySet):
    def upcoming(self):
        """Recurring rides, and one-time rides that have not left (or returned) yet."""
        # Dates are stored as datetime-local strings, e.g. "2026-10-12T08:30",
        # which sort the same way as the dates they stand for
        now = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        return self.filter(
            models.Q(one_time=False)
            | models.Q(leaving_at_date_time__gte=now)
            | models.Q(one_way=False, returning_at_date_time__gte=now)
        )

    def past(self):
        return self.exclude(pk__in=self.upcoming().values("pk"))

    def visible_to(self, user):
        """
        The rides user may see: rides posted to everyone, rides posted to a
        group user is a member of, and rides user drives or has asked to
        join (people keep seeing a ride they are part of, even after leaving
        its group). See groups/models.py.
        """
        from groups.models import Membership
        in_group = Ride.groups.through.objects.filter(
            ride=OuterRef("pk"),
            group__memberships__user=user,
            group__memberships__status=Membership.Status.ACTIVE,
        )
        asked = RideRequest.objects.filter(ride=OuterRef("pk"), passenger=user)
        return self.filter(
            models.Q(groups_only=False) | models.Q(driver=user) | models.Exists(in_group) | models.Exists(asked)
        )

    def with_seats_taken(self):
        """
        seats_taken: the accepted passengers; and for each day of the week
        (seats_taken_monday...), the accepted passengers on that day of a
        recurring ride (RideRequest.days).
        """
        accepted = models.Q(requests__status=RideRequest.Status.ACCEPTED)
        return self.annotate(
            seats_taken=models.Count("requests", filter=accepted),
            **{f"seats_taken_{day}": models.Count("requests", filter=accepted & on_day(day, "requests__days"))
               for day in WEEKDAY_KEYS},
        )

def on_day(day, field="days"):
    """Requests (RideRequest.days) to join a recurring ride on day: those for that day, or for all its days."""
    return models.Q(**{f"{field}__contains": [day]}) | models.Q(**{field: []})

class Ride(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="driver"
    )

    # Passengers are the accepted RideRequests (ride.requests)
    
    # Car Ride
    offer = models.BooleanField(default=False)
    request = models.BooleanField(default=False)

    # Other Transport
    train = models.BooleanField(default=False)
    bus = models.BooleanField(default=False)
    taxi = models.BooleanField(default=False)
    other = models.BooleanField(default=False)
    
    other_field = models.CharField(blank=True, null=True)
    max_passengers = models.IntegerField(blank=True, null=True)

    # Address
    start = models.CharField(blank=True, null=True)
    start_json = models.JSONField()
    start_location = models.PointField(geography=True, blank=True, null=True)

    # Vias are stored in the Via model (ride.via_points)

    destination = models.CharField(blank=True, null=True)
    destination_json = models.JSONField()
    destination_location = models.PointField(geography=True, blank=True, null=True)

    # Driving route from start through the vias to the destination, in metres
    # (EPSG:3067). Used to find rides passing by on the way; see rides/routes.py
    route = models.LineStringField(srid=3067, blank=True, null=True)

    # deprecated
    dest_name = models.CharField(help_text="Destination name", blank=True, null=True)

    # Schedule

    one_time = models.BooleanField(default=True)
    one_way = models.BooleanField(default=True)

    leaving_at_date_time = models.CharField(blank=True)
    # leaving_at_hour = models.IntegerField(blank=True)
    # leaving_at_minute = models.IntegerField(blank=True)

    returning_at_date_time = models.CharField(blank=True)
    # arriving_at_hour = models.IntegerField(blank=True)
    # arriving_at_minute = models.IntegerField(blank=True)

    # Recurring days

    monday_check = models.BooleanField(default=False)
    monday_leaving_at_time = models.CharField(blank=True)
    monday_returning_at_time = models.CharField(blank=True)

    tuesday_check = models.BooleanField(default=False)
    tuesday_leaving_at_time = models.CharField(blank=True)
    tuesday_returning_at_time = models.CharField(blank=True)

    wednesday_check = models.BooleanField(default=False)
    wednesday_leaving_at_time = models.CharField(blank=True)
    wednesday_returning_at_time = models.CharField(blank=True)

    thursday_check = models.BooleanField(default=False)
    thursday_leaving_at_time = models.CharField(blank=True)
    thursday_returning_at_time = models.CharField(blank=True)

    friday_check = models.BooleanField(default=False)
    friday_leaving_at_time = models.CharField(blank=True)
    friday_returning_at_time = models.CharField(blank=True)

    saturday_check = models.BooleanField(default=False)
    saturday_leaving_at_time = models.CharField(blank=True)
    saturday_returning_at_time = models.CharField(blank=True)

    sunday_check = models.BooleanField(default=False)
    sunday_leaving_at_time = models.CharField(blank=True)
    sunday_returning_at_time = models.CharField(blank=True)

    note = models.TextField(blank=True, default="", help_text="Any kind of note for passengers")
    price = models.CharField(max_length=100, blank=True, default="", help_text="Optional price for passengers, e.g. \"€10 per passenger\"")
    # The driver can leave at another time than the one given, e.g. one
    # agreed with the passengers
    flexible_time = models.BooleanField(default=False, help_text="The departure times are flexible")
    private = models.CharField(default=False)

    # Who sees the ride: everyone, or (groups_only) only the members of
    # groups, which are some of the driver's groups. A groups_only ride whose
    # groups are all gone is seen by nobody. See groups/models.py.
    groups_only = models.BooleanField(default=False)
    groups = models.ManyToManyField("groups.Group", blank=True, related_name="rides")

    created_at = models.DateTimeField("date added", auto_now_add=True)
    # When the driver last changed it on the edit ride page; None if never.
    # Not auto_now: the app saves rides itself too (e.g. their route).
    updated_at = models.DateTimeField("last updated", null=True, blank=True)

    objects = RideQuerySet.as_manager()

    def __str__(self):
        if self.start_json and self.destination_json:
            return f"From: {self.start_json["displayName"]}, Destination: {self.destination_json["displayName"]}"
        else:
            return f"From: {self.start}, Destination: {self.destination}"

    def is_hidden(self):
        """A ride posted only to groups that are all gone: nobody but the people in it sees it."""
        return self.groups_only and not self.groups.exists()

    def transport_options(self):
        """The ride's ways of travelling (car offer, request, train, ...) with their icons."""
        return [option for option in TRANSPORT_OPTIONS if getattr(self, option.field)]

    def route_name(self):
        return f"{self.start_json['displayName']} {self.sign()} {self.destination_json['displayName']}"

    def leaving_at(self):
        """When a one-time ride leaves, None for recurring rides or unreadable dates."""
        return parse_local(self.leaving_at_date_time) if self.one_time else None

    def returning_at(self):
        return parse_local(self.returning_at_date_time) if self.one_time and not self.one_way else None

    def days(self):
        """Short summary of a recurring ride's days, e.g. "Weekdays" or "Mon, Wed"."""
        day_filter = self.day_filter()
        if all(day_filter):
            return _("Every day")
        if all(day_filter[:5]) and not any(day_filter[5:7]):
            return _("Weekdays")
        if all(day_filter[5:7]) and not any(day_filter[:5]):
            return _("Weekends")
        return ", ".join(compress([_("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri"), _("Sat"), _("Sun")], day_filter))

    def day_filter(self):
        return [
            self.monday_check,
            self.tuesday_check,
            self.wednesday_check,
            self.thursday_check,
            self.friday_check,
            self.saturday_check,
            self.sunday_check,
        ]

    def departure_time(self):
        """When the ride leaves (a time), for recurring rides on its first day; None if unknown."""
        if self.one_time:
            leaving_at = self.leaving_at()
            return leaving_at.time() if leaving_at else None
        days = self.day_keys()
        return self.times_on(days[0])[0] if days else None

    def times_on(self, day):
        """
        When a recurring ride leaves and returns on day (WEEKDAY_KEYS), as
        times; returning is None for a one-way ride, and either for none set.
        """
        leaving = parse_time(getattr(self, f"{day}_leaving_at_time"))
        returning = None if self.one_way else parse_time(getattr(self, f"{day}_returning_at_time"))
        return leaving, returning

    # Seats. A one-time ride's seats are taken by its accepted passengers. A
    # recurring ride has its seats on each of its days: a passenger joins it
    # on some of them (RideRequest.days), and takes a seat on those only.
    # The counts come from RideQuerySet.with_seats_taken when present.

    def day_keys(self):
        """The keys of a recurring ride's days (WEEKDAY_KEYS), in order; none for one-time rides."""
        if self.one_time:
            return []
        return [day for day, checked in zip(WEEKDAY_KEYS, self.day_filter()) if checked]

    def seats_taken_on(self, day):
        taken = getattr(self, f"seats_taken_{day}", None)
        if taken is None:
            taken = self.requests.filter(on_day(day), status=RideRequest.Status.ACCEPTED).count()
        return taken

    def seats_left_on(self, day):
        """Free seats on day of a recurring ride, or None when the driver set no limit."""
        if self.max_passengers is None:
            return None
        return max(self.max_passengers - self.seats_taken_on(day), 0)

    def seats_left(self):
        """
        Free seats, or None when the driver set no limit. For a recurring
        ride, the most on any of its days (the ride is full when every day
        is), or those on seats_day when it is set (a search for a date).
        """
        if self.max_passengers is None:
            return None
        days = self.day_keys()
        if days:
            day = getattr(self, "seats_day", None)
            return self.seats_left_on(day) if day in days else max(self.seats_left_on(day) for day in days)
        taken = getattr(self, "seats_taken", None)
        if taken is None:
            taken = self.requests.filter(status=RideRequest.Status.ACCEPTED).count()
        return max(self.max_passengers - taken, 0)

    def is_full(self):
        return self.seats_left() == 0

    def most_seats_taken(self):
        """The most seats taken on any one trip: its passengers, or on a recurring ride its busiest day."""
        days = self.day_keys()
        if days:
            return max(self.seats_taken_on(day) for day in days)
        return self.requests.filter(status=RideRequest.Status.ACCEPTED).count()

    def seat_days(self):
        """
        A recurring ride's days, for choosing which to join and showing
        their seats: dicts of key, label ("Mondays"), leaving and returning
        (times, see times_on), seats_left (None without a limit) and full.
        """
        seat_days = []
        for day in self.day_keys():
            seats = self.seats_left_on(day)
            leaving, returning = self.times_on(day)
            seat_days.append({
                "key": day,
                "label": WEEKDAY_PLURALS[WEEKDAY_KEYS.index(day)],
                "leaving": leaving,
                "returning": returning,
                "seats_left": seats,
                "full": seats == 0,
            })
        return seat_days

    def sign(self):
        if self.one_way:
            return "→"
        else:
            return "⇄"

def parse_local(value):
    """A datetime-local string ("2026-10-12T08:30") as a naive datetime."""
    try:
        return datetime.strptime(value[:16], "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        return None

def parse_time(value):
    """A recurring ride's time string ("07:30") as a time, None if it has none."""
    try:
        return datetime.strptime(value[:5], "%H:%M").time()
    except (TypeError, ValueError):
        return None

def to_string(self):
    l = ""
    for var_name, var_val in vars(self).items():
        l += f"{var_name}: {var_val}\n"
    return l


class Via(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ride = models.ForeignKey(
        Ride,
        on_delete=models.CASCADE,
        related_name="via_points"
    )
    order = models.PositiveSmallIntegerField(default=0)
    via_json = models.JSONField()
    location = models.PointField(geography=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.via_json.get("displayName", "")


class RideRequest(models.Model):
    """
    A request to join a ride. The driver accepts or declines it; accepted
    requests are the ride's passengers. Withdrawing a request or leaving a
    ride deletes it, while a declined request stays so it cannot be resent.
    """
    class Status(models.TextChoices):
        PENDING = "pending", gettext_lazy("Pending")
        ACCEPTED = "accepted", gettext_lazy("Accepted")
        DECLINED = "declined", gettext_lazy("Declined")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name="requests")
    passenger = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ride_requests",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    # The days of a recurring ride the passenger joins it on (WEEKDAY_KEYS),
    # taking a seat on those only. Empty: all its days, as for one-time
    # rides and requests made before passengers chose days.
    days = ArrayField(models.CharField(max_length=10), blank=True, default=list)
    message = models.TextField(blank=True, default="", max_length=500, help_text="Message from the passenger to the driver")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # When the driver accepted it: a recurring ride's first trip together is
    # the first of the passenger's days after it (rides/ratings.py)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["ride", "passenger"], name="one_request_per_ride_and_passenger"),
        ]

    def __str__(self):
        return f"{self.passenger} → {self.ride} ({self.status})"

    def ride_days(self):
        """The keys of the ride's days the passenger joins it on: the chosen ones it still has, or all of them."""
        days = self.ride.day_keys()
        return [day for day in days if day in self.days] if self.days else days

    def day_labels(self):
        """The days the passenger joins the ride on, e.g. "Mondays, Wednesdays"; "" for a one-time ride."""
        return ", ".join(str(WEEKDAY_PLURALS[WEEKDAY_KEYS.index(day)]) for day in self.ride_days())

    def fits(self):
        """Whether accepting the request leaves no day of the ride over its seats."""
        ride = self.ride
        if ride.max_passengers is None:
            return True
        days = self.ride_days()
        if days:
            return all(ride.seats_left_on(day) > 0 for day in days)
        return not ride.is_full()



class Rating(models.Model):
    """
    A member's rating of a co-rider after a trip (rides/ratings.py): made
    waiting for an answer once the trip is over, then a score out of 10,
    or why they gave none. One per ride, rater and rated member; it can be
    changed while the trip can still be rated.
    """
    class Outcome(models.TextChoices):
        PENDING = "pending", gettext_lazy("Waiting for an answer")
        RATED = "rated", gettext_lazy("Rated")
        NO_SHOW = "no_show", gettext_lazy("Did not show up")
        SKIPPED = "skipped", gettext_lazy("Not rated")
        NOT_HAPPENED = "not_happened", gettext_lazy("The ride did not take place")

    class Tag(models.TextChoices):
        """What went well, ticked with a score. The last two are for drivers only (DRIVER_TAGS)."""
        ON_TIME = "on_time", gettext_lazy("On time")
        FRIENDLY = "friendly", gettext_lazy("Friendly")
        COMMUNICATION = "communication", gettext_lazy("Good communication")
        SAFE_DRIVING = "safe_driving", gettext_lazy("Safe driving")
        CLEAN_CAR = "clean_car", gettext_lazy("Comfortable car")

    class Review(models.TextChoices):
        """
        The co-riders' answers about each other disagree, e.g. one says the
        other did not show up and the other rated them (ratings.disputed):
        neither counts until the admins decide.
        """
        NONE = "", gettext_lazy("Not disputed")
        PENDING = "pending", gettext_lazy("Disputed, waiting for review")
        UPHELD = "upheld", gettext_lazy("Counted after review")
        DISCARDED = "discarded", gettext_lazy("Discarded after review")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Kept when the ride is deleted, so that the trip can still be rated and
    # the rating still counts; route keeps its name
    ride = models.ForeignKey(Ride, on_delete=models.SET_NULL, null=True, blank=True, related_name="ratings")
    route = models.CharField(max_length=300)
    rater = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings_given")
    rated = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings_received")
    rated_is_driver = models.BooleanField(default=False)
    # The day of the trip rated (a recurring ride's first trip together),
    # and when it can be rated from (ratings.RATE_AFTER after the trip)
    trip_date = models.DateField()
    due_at = models.DateTimeField()
    outcome = models.CharField(max_length=15, choices=Outcome.choices, default=Outcome.PENDING)
    # 1-10, only when outcome is RATED
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    tags = ArrayField(models.CharField(max_length=20, choices=Tag.choices), blank=True, default=list)
    # Only the admins see it
    comment = models.TextField(blank=True, default="", max_length=1000)
    review = models.CharField(max_length=10, choices=Review.choices, blank=True, default=Review.NONE)
    # Whether the rater was told the trip can be rated (ratings.remind)
    reminded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["rater", "due_at"]), models.Index(fields=["rated", "outcome"])]
        constraints = [
            models.UniqueConstraint(fields=["ride", "rater", "rated"], name="one_rating_per_ride_and_pair"),
            models.CheckConstraint(
                condition=models.Q(outcome="rated", score__gte=1, score__lte=10) | (~models.Q(outcome="rated") & models.Q(score=None)),
                name="score_only_when_rated",
            ),
            models.CheckConstraint(condition=~models.Q(rater=models.F("rated")), name="no_rating_oneself"),
        ]

    def __str__(self):
        return f"{self.rater} → {self.rated}: {self.score or self.get_outcome_display()}"

    def tag_choices(self):
        """The tags the rater can tick for the rated member, as (value, label)."""
        tags = DRIVER_TAGS if self.rated_is_driver else PASSENGER_TAGS
        return [(tag.value, tag.label) for tag in tags]

DRIVER_TAGS = list(Rating.Tag)
PASSENGER_TAGS = [Rating.Tag.ON_TIME, Rating.Tag.FRIENDLY, Rating.Tag.COMMUNICATION]


class Report(models.Model):
    """
    A member reporting another member to the admins, from a ride they
    share or that one of them posted (ride_detail.html). The admins are
    emailed (home.views.report_member) and mark it handled in the admin.
    """
    class Reason(models.TextChoices):
        SAFETY = "safety", gettext_lazy("Safety concern")
        BEHAVIOUR = "behaviour", gettext_lazy("Rude or inappropriate behaviour")
        MISLEADING = "misleading", gettext_lazy("Fake or misleading ride")
        PAYMENT = "payment", gettext_lazy("Payment problem")
        OTHER = "other", gettext_lazy("Something else")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made")
    reported = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_received")
    ride = models.ForeignKey(Ride, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    route = models.CharField(max_length=300, blank=True, default="")
    reason = models.CharField(max_length=15, choices=Reason.choices)
    message = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(null=True, blank=True)
    # The admins' notes on what was done
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reporter} → {self.reported}: {self.get_reason_display()}"
