from django.db import models
from django.contrib.gis.db import models
from django.conf import settings
from django.utils.translation import gettext as _, gettext_lazy
from django.utils import timezone
from itertools import compress
from dateutil import parser
from dateutil.parser import ParserError
from datetime import datetime
from django.utils import formats
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
        """The time the ride leaves, for recurring rides the time on its first day."""
        if self.one_time:
            leaving_at = self.leaving_at()
            return leaving_at.strftime("%H:%M") if leaving_at else ""
        first_day = next(self.weekly_schedule(), None)
        return first_day[1] if first_day else ""

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
        times, seats_left (None without a limit) and full.
        """
        times = {day: (getattr(self, f"{day}_leaving_at_time"), getattr(self, f"{day}_returning_at_time"))
                 for day in WEEKDAY_KEYS}
        seat_days = []
        for day in self.day_keys():
            seats = self.seats_left_on(day)
            seat_days.append({
                "key": day,
                "label": WEEKDAY_PLURALS[WEEKDAY_KEYS.index(day)],
                "leaving": times[day][0],
                "returning": "" if self.one_way else times[day][1],
                "seats_left": seats,
                "full": seats == 0,
            })
        return seat_days

    def get_created_at(self):
        return formats.date_format(self.created_at, "Y.m.d")

    # Very janky TEMPORARY system please someone replace it with a better one
    def parse_date(self, display_format):
        parse_format = "%Y-%m-%d %H:%M:%S"

        try:
            l_date = parser.parse(self.leaving_at_date_time)
            l_date_datetime = datetime.strptime(str(l_date), parse_format)
            l_date_formatted = datetime.strftime(l_date_datetime, display_format)
        except ParserError:
            l_date_formatted = ""

        try:
            r_date = parser.parse(self.returning_at_date_time)
            r_date_datetime = datetime.strptime(str(r_date), parse_format)
            r_date_formatted = datetime.strftime(r_date_datetime, display_format)
        except ParserError:
            r_date_formatted = ""
        
        return l_date_formatted, r_date_formatted
    
    def schedule(self):
        schedule_string = ""
        template = '''<div class="col-span-2 badge badge-soft badge-info rounded-full badge-lg">
            {0}
        </div>
        '''
        if self.one_time:
            
            l_date_formatted, r_date_formatted = self.parse_date("%d.%m  <b>%H:%M</b>")

            if self.one_way:
                schedule_string = template.format(l_date_formatted)
                # schedule_string = "test"
            else:      
                schedule_string = template.format(l_date_formatted) + template.format(r_date_formatted)
        else:
            day_filter = [
                self.monday_check, 
                self.tuesday_check, 
                self.wednesday_check, 
                self.thursday_check, 
                self.friday_check, 
                self.saturday_check, 
                self.sunday_check
            ]

            days = [
                _("Mon"), 
                _("Tue"), 
                _("Wed"), 
                _("Thu"), 
                _("Fri"), 
                _("Sat"), 
                _("Sun")
            ]



            if all(day_filter):
                schedule_string = template.format(_("Every day"))
            elif all(day_filter[:5]) and not any(day_filter[5:7]):
                schedule_string = template.format(_("Weekdays"))
            elif all(day_filter[5:7]) and not any(day_filter[:5]):
                schedule_string = template.format(_("Weekends"))
            else:
                days = compress(days, day_filter)
                joint_string = ", ".join(days)
                # schedule_string = "".join([template.format(day) for day in days])
                args = "rounded-full"

                if 2 < sum(day_filter) < 4:
                    args = "h-20"
                elif sum(day_filter) > 3:
                    args = "h-20"
                    
                schedule_string = f'''<div class="col-span-2 badge badge-soft badge-info badge-lg {args}">
                        {joint_string}
                    </div>'''

        return schedule_string

    def schedule_long(self):
            if self.one_time:

                l_date_formatted, r_date_formatted = self.parse_date("%Y.%d.%m  <b>%H:%M</b>")
                
                if self.one_way:
                    schedule_string = l_date_formatted
                else:      
                    schedule_string = f"<p>{r_date_formatted}</p> {self.sign()} <p>{l_date_formatted}</p>"
            else:
                schedule_string = ""
    
            return schedule_string

    def weekly_schedule(self):
        day_filter = [
            self.monday_check, 
            self.tuesday_check, 
            self.wednesday_check, 
            self.thursday_check, 
            self.friday_check, 
            self.saturday_check, 
            self.sunday_check
        ]

        days = WEEKDAY_PLURALS

        # Datastructures are for suckers and losers

        schedule_array = [
            (
                days[0], 
                self.monday_leaving_at_time, 
                self.monday_returning_at_time
            ),
            (
                days[1], 
                self.tuesday_leaving_at_time, 
                self.tuesday_returning_at_time
            ),
            (
                days[2], 
                self.wednesday_leaving_at_time, 
                self.wednesday_returning_at_time
            ),
            (
                days[3], 
                self.thursday_leaving_at_time, 
                self.thursday_returning_at_time
            ),
            (
                days[4], 
                self.friday_leaving_at_time, 
                self.friday_returning_at_time
            ),
            (
                days[5], 
                self.saturday_leaving_at_time, 
                self.saturday_returning_at_time
            ),
            (
                days[6], 
                self.sunday_leaving_at_time, 
                self.sunday_returning_at_time
            ),
        ]

        return compress(schedule_array, day_filter)

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
