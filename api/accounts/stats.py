"""
User statistics for the admin (CustomUserAdmin.stats_view): numbers, charts
and a table of users, for the users and the period chosen in StatsFilterForm.

The period limits what is counted (sign-ups, rides posted, requests made,
notifications, events of the activity log); the users are everyone who had
joined by the end of it. Much of it comes from the activity log
(activity/models.py), which only has what happened after it was added, so
those numbers start from its first event (UserStats.log_start). The
test user and the random test rides (rides/admin.py) are left out of all of
it, so that they do not skew the numbers. The
table's rows (UserStats.user_rows, COLUMNS) are also downloaded as CSV, with
one column for each number, for analysing elsewhere.
"""
import statistics
from datetime import datetime, time, timedelta

from django import forms
from django.db.models import Count, DurationField, Exists, ExpressionWrapper, F, IntegerField, Max, OuterRef, Q, Subquery
from django.db.models.fields.json import KT
from django.db.models.functions import Coalesce, ExtractHour, ExtractIsoWeekDay, TruncMonth, TruncWeek
from django.utils import formats, timezone
from django.utils.translation import gettext_lazy as _, ngettext

from activity.models import Event, Kind
from home.campuses import CAMPUSES
from notifications.models import Notification, PushSubscription
from rides.admin import TEST_RIDE_KEY, TEST_USER_EMAIL
from rides.models import Ride, RideRequest, parse_local
from rides.transport import TRANSPORT_OPTIONS
from .forms import ALLOWED_EMAIL_DOMAINS
from .models import User

# Left out of every number: the test user, and the test rides with everything
# to do with them (requests to them, notifications about them). The test
# user drives the test rides, but rides can also be marked as test rides.
TEST_USER = Q(email__iexact=TEST_USER_EMAIL)


def _test_rides(ride=""):
    """Test rides; ride is the path to the ride, e.g. "ride__" for requests."""
    # contains, as a missing key would make start_json__test_ride NULL, and
    # NULL in an exclude() leaves out every other ride too
    return Q(**{f"{ride}driver__email__iexact": TEST_USER_EMAIL}) | Q(**{f"{ride}start_json__contains": {TEST_RIDE_KEY: True}})


# Periods up to this long are charted by week, longer ones by month
WEEKLY_UP_TO = timedelta(days=180)

# Events that are something the user did in the app, not just being there
# (for the hours and days the app is used)
ACTIONS = [kind for kind in Kind if kind not in (Kind.ACTIVE, Kind.LOGGED_IN, Kind.LOGGED_OUT, Kind.ACCOUNT_DELETED)]

# The retention table's months after joining (30-day months)
RETENTION_MONTHS = [1, 2, 3, 6, 12]


class StatsFilterForm(forms.Form):
    period = forms.ChoiceField(required=False, label=_("Period"), choices=[
        ("all", _("All time")),
        ("30", _("Last 30 days")),
        ("90", _("Last 90 days")),
        ("365", _("Last 12 months")),
        ("custom", _("Custom range")),
    ])
    start = forms.DateField(required=False, label=_("From"), widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(required=False, label=_("To"), widget=forms.DateInput(attrs={"type": "date"}))
    domain = forms.ChoiceField(required=False, label=_("Email domain"),
        choices=[("", _("All domains"))] + [(domain, domain) for domain in ALLOWED_EMAIL_DOMAINS])
    confirmed = forms.ChoiceField(required=False, label=_("Email address"), choices=[
        ("", _("Confirmed or not")),
        ("yes", _("Confirmed")),
        ("no", _("Not confirmed")),
    ])

    def clean(self):
        data = super().clean()
        if data.get("period") == "custom" and data.get("start") and data.get("end") and data["start"] > data["end"]:
            raise forms.ValidationError(_("The start of the period is after its end."))
        return data

    def choices(self):
        """The cleaned choices, or the defaults (all users, all time) for missing or invalid ones."""
        return self.cleaned_data if self.is_bound and self.is_valid() else {}


def _day_start(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _period(choices, now):
    """(start, end) of the chosen period: start is None for all time, end is not included."""
    period = choices.get("period") or "all"
    if period == "custom":
        start, end = choices.get("start"), choices.get("end")
        return (start and _day_start(start)), (_day_start(end + timedelta(days=1)) if end else now)
    if period == "all":
        return None, now
    return now - timedelta(days=int(period)), now


def _percent(part, whole):
    return round(100 * part / whole) if whole else 0


def _duration(delta):
    """A short, rough length of time: 25 min, 3.5 h, 2.0 d."""
    if delta is None:
        return "–"
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{round(hours * 60)} min"
    if hours < 48:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} d"


def _domain(email):
    return email.rsplit("@", 1)[-1].lower()


def _iso(value):
    return timezone.localtime(value).isoformat(timespec="seconds") if value else ""


# The table's and the CSV's columns: (key, label, value of a row from
# user_rows). The CSV has all of them, with the keys as its header; the
# page's table has the ones in TABLE_COLUMNS. Counts are for the period.
COLUMNS = [
    ("id", _("User ID"), lambda u: u.pk),
    ("email", _("Email"), lambda u: u.email),
    ("domain", _("Domain"), lambda u: _domain(u.email)),
    ("first_name", _("First name"), lambda u: u.first_name),
    ("last_name", _("Last name"), lambda u: u.last_name),
    ("date_joined", _("Joined"), lambda u: _iso(u.date_joined)),
    ("email_confirmed_at", _("Email confirmed"), lambda u: _iso(u.email_confirmed_at)),
    ("last_login", _("Last login"), lambda u: _iso(u.last_login)),
    ("welcomed_at", _("Saw the welcome popup"), lambda u: _iso(u.welcomed_at)),
    ("is_active", _("Active account"), lambda u: u.is_active),
    ("is_staff", _("Staff"), lambda u: u.is_staff),
    ("has_photo", _("Has a photo"), lambda u: bool(u.pfp)),
    ("has_phone", _("Has a phone number"), lambda u: bool(u.phone)),
    ("name_visibility", _("Name shown"), lambda u: u.name_visibility),
    ("show_photo", _("Shows photo"), lambda u: u.show_photo),
    ("share_email", _("Shares email"), lambda u: u.share_email),
    ("share_phone", _("Shares phone"), lambda u: u.share_phone),
    ("email_notifications", _("Emailed notifications"), lambda u: u.email_notifications),
    ("push_devices", _("Push devices"), lambda u: u.push_devices),
    ("rides_posted", _("Rides posted"), lambda u: u.rides_posted),
    ("requests_made", _("Requests made"), lambda u: u.requests_made),
    ("requests_accepted", _("Requests accepted"), lambda u: u.requests_accepted),
    ("requests_declined", _("Requests declined"), lambda u: u.requests_declined),
    ("requests_pending", _("Requests pending"), lambda u: u.requests_made - u.requests_accepted - u.requests_declined),
    ("requests_received", _("Requests received"), lambda u: u.requests_received),
    ("requests_received_accepted", _("Received requests accepted"), lambda u: u.requests_received_accepted),
    ("notifications_received", _("Notifications"), lambda u: u.notifications_received),
    ("notifications_read", _("Notifications read"), lambda u: u.notifications_read),
    # From the activity log
    ("last_active", _("Last active"), lambda u: _iso(u.last_active)),
    ("active_days", _("Days active"), lambda u: u.active_days),
    ("searches", _("Searches"), lambda u: u.searches),
    ("rides_viewed", _("Rides opened"), lambda u: u.rides_viewed),
    ("rides_deleted", _("Rides deleted"), lambda u: u.rides_deleted),
    ("requests_withdrawn", _("Requests withdrawn or rides left"), lambda u: u.requests_withdrawn),
]
TABLE_COLUMNS = ["email", "date_joined", "last_login", "active_days", "searches", "rides_posted", "requests_made",
                 "requests_accepted", "requests_received", "requests_received_accepted", "push_devices"]
# The columns the table can be sorted by, and what they sort by
SORTS = {key: key for key in TABLE_COLUMNS}
DEFAULT_SORT = "-date_joined"


class UserStats:
    def __init__(self, form):
        choices = form.choices()
        self.now = timezone.now()
        self.start, self.end = _period(choices, self.now)

        users = User.objects.exclude(TEST_USER).filter(date_joined__lt=self.end)
        if choices.get("domain"):
            users = users.filter(email__iendswith="@" + choices["domain"])
        if choices.get("confirmed"):
            users = users.filter(email_confirmed_at__isnull=choices["confirmed"] == "no")
        self.users = users
        self.rides = Ride.objects.filter(driver__in=users, **self._in_period("created_at")).exclude(_test_rides())
        self.requests = (RideRequest.objects.filter(passenger__in=users, **self._in_period("created_at"))
                         .exclude(_test_rides("ride__")))
        # The activity log has no events of the test user or about test rides.
        # Anonymised events (activity/events.py) belong to no one, so they
        # count only when the users are not filtered.
        events = Event.objects.filter(**self._in_period("created_at")).exclude(kind=Kind.ACCOUNT_DELETED)
        if choices.get("domain") or choices.get("confirmed"):
            self.events = events.filter(user__in=users)
        else:
            self.events = events.filter(Q(user__in=users) | Q(user__isnull=True))
        deleted = Event.objects.filter(kind=Kind.ACCOUNT_DELETED, **self._in_period("created_at"))
        if choices.get("domain"):
            deleted = deleted.filter(data__domain=choices["domain"])
        self.deleted_accounts = deleted
        self.log_start = Event.objects.order_by("created_at").values_list("created_at", flat=True).first()

    def _in_period(self, field):
        within = {f"{field}__lt": self.end}
        if self.start:
            within[f"{field}__gte"] = self.start
        return within

    def log_label(self):
        """Since when the activity log has events, for the numbers that come from it."""
        if not self.log_start:
            return _("The activity log has no events yet.")
        return _("From the activity log, which starts on %(date)s.") % {
            "date": formats.date_format(timezone.localtime(self.log_start).date())}

    def period_label(self):
        if not self.start:
            return _("All time")
        last_day = timezone.localtime(self.end - timedelta(microseconds=1)).date()
        return f"{formats.date_format(timezone.localtime(self.start).date())} – {formats.date_format(last_day)}"

    # The numbers at the top of the page

    def tiles(self):
        """(label, value, note) of each number."""
        week, month = self.now - timedelta(days=7), self.now - timedelta(days=30)
        users = self.users.aggregate(
            total=Count("pk"),
            new=Count("pk", filter=Q(**self._in_period("date_joined"))),
            confirmed=Count("pk", filter=Q(email_confirmed_at__isnull=False)),
            active_week=Count("pk", filter=Q(last_login__gte=week)),
            active_month=Count("pk", filter=Q(last_login__gte=month)),
            **{domain: Count("pk", filter=Q(email__iendswith="@" + domain)) for domain in ALLOWED_EMAIL_DOMAINS},
        )
        requests = self.requests.aggregate(
            total=Count("pk"),
            passengers=Count("passenger", distinct=True),
            accepted=Count("pk", filter=Q(status=RideRequest.Status.ACCEPTED)),
            declined=Count("pk", filter=Q(status=RideRequest.Status.DECLINED)),
        )
        rides = self.rides.aggregate(total=Count("pk"), drivers=Count("driver", distinct=True))
        answered = requests["accepted"] + requests["declined"]
        # updated_at: when the request was last changed, usually its answer
        waits = list(
            self.requests.exclude(status=RideRequest.Status.PENDING)
            .annotate(wait=ExpressionWrapper(F("updated_at") - F("created_at"), output_field=DurationField()))
            .values_list("wait", flat=True)
        )
        domains = " · ".join(f"{domain} {users[domain]}" for domain in ALLOWED_EMAIL_DOMAINS)
        return [
            (_("Users"), users["total"], domains),
            (_("New sign-ups"), users["new"], self.period_label()),
            (_("Email confirmed"), f"{_percent(users['confirmed'], users['total'])} %",
             _("%(count)s of %(total)s users") % {"count": users["confirmed"], "total": users["total"]}),
            (_("Active in the last 30 days"), users["active_month"],
             _("%(count)s in the last 7 days") % {"count": users["active_week"]}),
            (_("Drivers"), rides["drivers"],
             ngettext("%(count)s ride posted", "%(count)s rides posted", rides["total"]) % {"count": rides["total"]}),
            (_("Passengers"), requests["passengers"],
             ngettext("%(count)s request made", "%(count)s requests made", requests["total"]) % {"count": requests["total"]}),
            (_("Requests accepted"), f"{_percent(requests['accepted'], answered)} %",
             _("of %(count)s answered requests") % {"count": answered}),
            (_("Median time to answer"), _duration(statistics.median(waits) if waits else None),
             _("from request to accepted or declined")),
            *self._engagement_tiles(),
        ]

    def _engagement_tiles(self):
        """Tiles about how much the app is used and how well rides fill up."""
        # Stickiness: of the users active in the last 30 days, the share
        # active on an average day (daily / monthly active users)
        month = self.now - timedelta(days=30)
        active = Event.objects.filter(user__in=self.users, kind=Kind.ACTIVE, created_at__gte=month)
        monthly = active.values("user").distinct().count()
        daily = active.count() / 30

        searches = self.events.filter(kind=Kind.SEARCHED).aggregate(
            total=Count("pk"), empty=Count("pk", filter=Q(data__results=0)),
            searchers=Count("user", distinct=True))
        asked = self.events.filter(kind=Kind.SEARCHED).filter(
            Exists(self.requests.filter(passenger=OuterRef("user")))).values("user").distinct().count()

        # Seats offered in car rides with a set number of seats, and taken
        seats = list(self.rides.filter(offer=True, max_passengers__gt=0).with_seats_taken()
                     .values_list("max_passengers", "seats_taken"))
        offered, taken = sum(s for s, _t in seats), sum(min(s, t) for s, t in seats)
        offers = self.rides.filter(offer=True)
        unanswered = offers.exclude(Exists(RideRequest.objects.filter(ride=OuterRef("pk")))).count()

        lost = self.events.filter(kind__in=[Kind.REQUEST_WITHDRAWN, Kind.PASSENGER_LEFT, Kind.PASSENGER_REMOVED])
        cancelled = self.events.filter(kind=Kind.RIDE_DELETED, data__upcoming=True, data__passengers__gt=0)

        total = self.users.count()
        partners = self._with_ride_partner().count()
        deleted = list(self.deleted_accounts.values_list("data__days", flat=True))

        return [
            (_("Stickiness"), f"{_percent(daily, monthly)} %",
             _("%(daily)s active a day on average, %(monthly)s in the last 30 days") % {
                 "daily": round(daily, 1), "monthly": monthly}),
            (_("Searches"), searches["total"],
             _("%(percent)s %% found no rides") % {"percent": _percent(searches["empty"], searches["total"])}),
            (_("Searchers who asked to join"), f"{_percent(asked, searches['searchers'])} %",
             _("of %(count)s users who searched") % {"count": searches["searchers"]}),
            (_("Seats filled"), f"{_percent(taken, offered)} %",
             _("of %(count)s seats offered in car rides") % {"count": offered}),
            (_("Car rides without requests"), f"{_percent(unanswered, offers.count())} %",
             _("%(count)s of %(total)s rides offered") % {"count": unanswered, "total": offers.count()}),
            (_("Trips called off"), lost.count() + cancelled.count(),
             _("%(requests)s requests withdrawn, passengers left or removed; %(rides)s rides with passengers cancelled")
             % {"requests": lost.count(), "rides": cancelled.count()}),
            (_("Have shared a ride"), f"{_percent(partners, total)} %",
             _("%(count)s users have driven or been a passenger with someone") % {"count": partners}),
            (_("Accounts deleted"), len(deleted),
             _("after %(days)s days as a member (median)") % {"days": round(statistics.median(deleted))}
             if deleted else self.period_label()),
        ]

    def _with_ride_partner(self):
        """The users who have shared a ride: driven an accepted passenger, or been one."""
        shared = (RideRequest.objects.filter(status=RideRequest.Status.ACCEPTED)
                  .exclude(_test_rides("ride__")).exclude(passenger__email__iexact=TEST_USER_EMAIL))
        return self.users.filter(Exists(shared.filter(passenger=OuterRef("pk"))) | Exists(shared.filter(ride__driver=OuterRef("pk"))))

    # Charts: each has an id, a title and subtitle, its kind (line, bar or
    # hbar, a horizontal bar chart), its labels and series ({name, data}),
    # and rows for its table view. static/js/admin-stats.js draws them.

    def charts(self):
        charts = [*self._timelines(), *self._engagement_timelines(), self._funnel(), self._outcomes(),
                  self._called_off(), self._campuses(), self._lead_time(), self._transport(), self._hours(),
                  self._weekdays(), self._features(), self._devices(), self._recency(), self._settings(),
                  self._name_visibility()]
        for chart in charts:
            if chart["kind"] == "hbar":
                chart["height"] = 40 + 36 * len(chart["labels"])
            chart["rows"] = [[label, *(series["data"][i] for series in chart["series"])]
                             for i, label in enumerate(chart["labels"])]
        return charts

    def _buckets(self):
        """The first day of each week or month of the period, and the Trunc function for them."""
        first = self.start or self.users.order_by("date_joined").values_list("date_joined", flat=True).first() or self.now
        weekly = self.end - first <= WEEKLY_UP_TO
        day = timezone.localtime(first).date()
        last = timezone.localtime(self.end).date()
        if weekly:
            day -= timedelta(days=day.weekday())
        else:
            day = day.replace(day=1)
        buckets = []
        while day <= last:
            buckets.append(day)
            day = day + timedelta(days=7) if weekly else (day.replace(day=28) + timedelta(days=4)).replace(day=1)
        return buckets, (TruncWeek if weekly else TruncMonth), weekly

    def _per_bucket(self, queryset, field, trunc, buckets, count=None):
        """How many of queryset (or of distinct count, e.g. Count("user", distinct=True)) are in each bucket."""
        counts = dict(
            queryset.order_by().annotate(bucket=trunc(field)).values("bucket")
            .annotate(n=count or Count("pk")).values_list("bucket", "n")
        )
        counts = {timezone.localtime(bucket).date(): n for bucket, n in counts.items()}
        return [counts.get(day, 0) for day in buckets]

    def _timelines(self):
        buckets, trunc, weekly = self._buckets()
        labels = [formats.date_format(day, "j M Y" if weekly else "M Y") for day in buckets]
        unit = _("week") if weekly else _("month")

        signups = self._per_bucket(self.users.filter(**self._in_period("date_joined")), "date_joined", trunc, buckets)
        total = self.users.filter(date_joined__lt=self.start).count() if self.start else 0
        cumulative = []
        for count in signups:
            total += count
            cumulative.append(total)

        return [
            {"id": "users", "kind": "line", "fill": True, "title": _("Users"),
             "subtitle": _("All users who had joined by the end of each %(unit)s") % {"unit": unit},
             "labels": labels, "series": [{"name": _("Users"), "data": cumulative}]},
            {"id": "signups", "kind": "bar", "title": _("New sign-ups"),
             "subtitle": _("Accounts created each %(unit)s") % {"unit": unit},
             "labels": labels, "series": [{"name": _("Sign-ups"), "data": signups}]},
            {"id": "activity", "kind": "line", "wide": True, "title": _("Rides and requests"),
             "subtitle": _("Rides posted and requests to join a ride made each %(unit)s") % {"unit": unit},
             "labels": labels, "series": [
                 {"name": _("Rides posted"), "data": self._per_bucket(self.rides, "created_at", trunc, buckets)},
                 {"name": _("Requests made"), "data": self._per_bucket(self.requests, "created_at", trunc, buckets)},
             ]},
        ]

    def _engagement_timelines(self):
        buckets, trunc, weekly = self._buckets()
        labels = [formats.date_format(day, "j M Y" if weekly else "M Y") for day in buckets]
        unit = _("week") if weekly else _("month")
        users = Count("user", distinct=True)
        searches = self.events.filter(kind=Kind.SEARCHED)
        return [
            {"id": "active", "kind": "line", "wide": True, "title": _("Active users"),
             "subtitle": _("Users who used the app, and who searched for rides, each %(unit)s. %(log)s")
             % {"unit": unit, "log": self.log_label()},
             "labels": labels, "series": [
                 {"name": _("Active users"), "data": self._per_bucket(
                     self.events.filter(kind=Kind.ACTIVE), "created_at", trunc, buckets, users)},
                 {"name": _("Searched"), "data": self._per_bucket(searches, "created_at", trunc, buckets, users)},
             ]},
            {"id": "searches", "kind": "line", "title": _("Searches"),
             "subtitle": _("Searches each %(unit)s, and those that found no rides: demand that is not met")
             % {"unit": unit},
             "labels": labels, "series": [
                 {"name": _("Searches"), "data": self._per_bucket(searches, "created_at", trunc, buckets)},
                 {"name": _("Found no rides"), "data": self._per_bucket(
                     searches.filter(data__results=0), "created_at", trunc, buckets)},
             ]},
        ]

    def _funnel(self):
        """How far the users who joined in the period got. Each step counts the users at it or further."""
        joined = self.users.filter(**self._in_period("date_joined"))
        did = lambda *kinds: Exists(Event.objects.filter(user=OuterRef("pk"), kind__in=kinds))
        shared = self._with_ride_partner().filter(pk__in=joined.values("pk"))
        acted = joined.filter(Exists(Ride.objects.filter(driver=OuterRef("pk")).exclude(_test_rides()))
                              | Exists(RideRequest.objects.filter(passenger=OuterRef("pk")).exclude(_test_rides("ride__")))
                              | Q(pk__in=shared.values("pk")))
        looked = joined.filter(did(Kind.SEARCHED, Kind.RIDE_VIEWED) | Q(pk__in=acted.values("pk")))
        confirmed = joined.filter(Q(email_confirmed_at__isnull=False) | Q(pk__in=looked.values("pk")))
        steps = [
            (_("Signed up"), joined.count()),
            (_("Confirmed the email address"), confirmed.count()),
            (_("Searched or opened a ride"), looked.count()),
            (_("Posted a ride or asked to join one"), acted.count()),
            (_("Shared a ride"), shared.count()),
        ]
        return {"id": "funnel", "kind": "hbar", "title": _("From sign-up to sharing a ride"),
                "subtitle": _("Users who joined in the period, by how far they got. Searching and opening rides is "
                              "from the activity log."),
                "labels": [label for label, _count in steps],
                "series": [{"name": _("Users"), "data": [count for _label, count in steps]}]}

    def _called_off(self):
        counts = dict(self.events.filter(kind__in=[
            Kind.REQUEST_WITHDRAWN, Kind.PASSENGER_LEFT, Kind.REQUEST_DECLINED, Kind.PASSENGER_REMOVED,
        ]).order_by().values("kind").annotate(n=Count("pk")).values_list("kind", "n"))
        counts["cancelled"] = self.events.filter(kind=Kind.RIDE_DELETED, data__upcoming=True,
                                                 data__passengers__gt=0).count()
        labels = {
            Kind.REQUEST_WITHDRAWN: _("Requests withdrawn"), Kind.PASSENGER_LEFT: _("Passengers who left"),
            Kind.REQUEST_DECLINED: _("Requests declined"), Kind.PASSENGER_REMOVED: _("Passengers removed"),
            "cancelled": _("Rides cancelled with passengers"),
        }
        return {"id": "called_off", "kind": "hbar", "title": _("Trips that fell through"),
                "subtitle": _("In the period. %(log)s") % {"log": self.log_label()},
                "labels": list(labels.values()),
                "series": [{"name": _("Times"), "data": [counts.get(key, 0) for key in labels]}]}

    def _campuses(self):
        """Searches for rides to each campus against the rides posted to it: where demand is not met."""
        searched = dict(self.events.filter(kind=Kind.SEARCHED, data__destination_campus__isnull=False)
                        .order_by().annotate(campus=KT("data__destination_campus")).values("campus")
                        .annotate(n=Count("pk")).values_list("campus", "n"))
        posted = dict(self.rides.order_by().annotate(place=KT("destination_json__id")).values("place")
                      .annotate(n=Count("pk")).values_list("place", "n"))
        names = [(campus["label"], campus["place"]["displayName"], campus["place"]["id"]) for campus in CAMPUSES]
        return {"id": "campuses", "kind": "hbar", "title": _("Campuses: searches and rides"),
                "subtitle": _("Searches for rides to each campus, and rides posted to it, in the period"),
                "labels": [label for label, _name, _id in names],
                "series": [
                    {"name": _("Searches"), "data": [searched.get(name, 0) for _label, name, _id in names]},
                    {"name": _("Rides posted"), "data": [posted.get(place, 0) for _label, _name, place in names]},
                ]}

    def _lead_time(self):
        """How long before leaving one-time rides are posted."""
        labels = [_("Same day"), _("The day before"), _("2–7 days before"), _("Over a week before")]
        counts = [0] * len(labels)
        for created_at, leaving in self.rides.filter(one_time=True).values_list("created_at", "leaving_at_date_time"):
            leaving_at = parse_local(leaving)
            if leaving_at is None:
                continue
            days = (leaving_at.date() - timezone.localtime(created_at).date()).days
            counts[0 if days <= 0 else 1 if days == 1 else 2 if days <= 7 else 3] += 1
        return {"id": "lead_time", "kind": "hbar", "title": _("How far ahead rides are posted"),
                "subtitle": _("One-time rides posted in the period, by how long before leaving"),
                "labels": labels, "series": [{"name": _("Rides"), "data": counts}]}

    def _hours(self):
        counts = dict(self.events.filter(kind__in=ACTIONS).order_by().annotate(hour=ExtractHour("created_at"))
                      .values("hour").annotate(n=Count("pk")).values_list("hour", "n"))
        return {"id": "hours", "kind": "bar", "title": _("Time of day"),
                "subtitle": _("Things done in the app by hour (Finnish time). %(log)s") % {"log": self.log_label()},
                "labels": [f"{hour:02}" for hour in range(24)],
                "series": [{"name": _("Actions"), "data": [counts.get(hour, 0) for hour in range(24)]}]}

    def _weekdays(self):
        counts = dict(self.events.filter(kind__in=ACTIONS).order_by().annotate(day=ExtractIsoWeekDay("created_at"))
                      .values("day").annotate(n=Count("pk")).values_list("day", "n"))
        days = [_("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri"), _("Sat"), _("Sun")]
        return {"id": "weekdays", "kind": "bar", "title": _("Day of the week"),
                "subtitle": _("Things done in the app by day of the week. %(log)s") % {"log": self.log_label()},
                "labels": days, "series": [{"name": _("Actions"), "data": [counts.get(day, 0) for day in range(1, 8)]}]}

    def _features(self):
        """Of the users active in the period, the share who used each part of the app."""
        active = self.events.values("user").distinct().count()
        features = [
            (_("Searched for rides"), [Kind.SEARCHED]),
            (_("Opened a ride"), [Kind.RIDE_VIEWED]),
            (_("Asked to join a ride"), [Kind.REQUEST_SENT]),
            (_("Posted a ride"), [Kind.RIDE_POSTED]),
            (_("Answered a request"), [Kind.REQUEST_ACCEPTED, Kind.REQUEST_DECLINED]),
            (_("Opened a notification"), [Kind.NOTIFICATION_OPENED]),
            (_("Turned push notifications on"), [Kind.PUSH_ON]),
            (_("Changed the profile or photo"), [Kind.PROFILE_SAVED, Kind.PHOTO_ADDED, Kind.PHOTO_REMOVED]),
            (_("Changed the settings"), [Kind.SETTINGS_SAVED]),
        ]
        users = self.events.order_by().aggregate(**{
            str(i): Count("user", distinct=True, filter=Q(kind__in=kinds)) for i, (_label, kinds) in enumerate(features)
        })
        return {"id": "features", "kind": "hbar", "percent": True, "title": _("What people use"),
                "subtitle": _("Share of the %(count)s users active in the period, in per cent. %(log)s")
                % {"count": active, "log": self.log_label()},
                "labels": [label for label, _kinds in features],
                "series": [{"name": _("Users"), "data": [_percent(users[str(i)], active) for i in range(len(features))]}]}

    def _devices(self):
        counts = dict(self.events.filter(kind=Kind.ACTIVE).order_by().annotate(device=KT("data__device"))
                      .values("device").annotate(n=Count("pk")).values_list("device", "n"))
        return {"id": "devices", "kind": "hbar", "title": _("Phone or computer"),
                "subtitle": _("Days the app was used, by the device it was first used on that day"),
                "labels": [_("Phone"), _("Computer")],
                "series": [{"name": _("Days"), "data": [counts.get("mobile", 0), counts.get("desktop", 0)]}]}

    def retention(self):
        """
        The retention table: users by the month they joined, and the share of
        them who used the app in each of RETENTION_MONTHS after joining (30-day
        months; "" for months that have not ended yet). Only users who joined
        after the activity log started, as earlier activity is not in it.
        """
        if not self.log_start:
            return []
        joined = self.users.filter(date_joined__gte=self.log_start, **self._in_period("date_joined"))
        joined_at = dict(joined.values_list("pk", "date_joined"))
        cohorts = {}
        for pk, date_joined in joined_at.items():
            month = timezone.localtime(date_joined).date().replace(day=1)
            cohorts.setdefault(month, {})[pk] = date_joined
        if not cohorts:
            return []

        # The months after joining that each user was active in
        active = {}
        days = Event.objects.filter(user__in=joined, kind=Kind.ACTIVE).order_by().values_list("user", "created_at")
        for pk, created_at in days:
            active.setdefault(pk, set()).add((created_at - joined_at[pk]).days // 30)

        rows = []
        for month in sorted(cohorts, reverse=True):
            members = cohorts[month]
            cells = []
            for after in RETENTION_MONTHS:
                # Only the users for whom the month has ended
                reached = [pk for pk, date_joined in members.items()
                           if date_joined + timedelta(days=30 * (after + 1)) <= self.now]
                stayed = sum(1 for pk in reached if after in active.get(pk, ()))
                cells.append(f"{_percent(stayed, len(reached))} %" if reached else "")
            rows.append((formats.date_format(month, "M Y"), len(members), cells))
        return rows

    def _outcomes(self):
        counts = dict(self.requests.order_by().values("status").annotate(n=Count("pk")).values_list("status", "n"))
        statuses = [RideRequest.Status.ACCEPTED, RideRequest.Status.PENDING, RideRequest.Status.DECLINED]
        return {"id": "outcomes", "kind": "hbar", "title": _("Requests by answer"),
                "subtitle": _("Requests made in the period, by their answer now"),
                "labels": [status.label for status in statuses],
                "colors": ["good", "warning", "critical"],
                "series": [{"name": _("Requests"), "data": [counts.get(status, 0) for status in statuses]}]}

    def _transport(self):
        counts = self.rides.aggregate(**{o.field: Count("pk", filter=Q(**{o.field: True})) for o in TRANSPORT_OPTIONS})
        options = sorted(TRANSPORT_OPTIONS, key=lambda o: -counts[o.field])
        return {"id": "transport", "kind": "hbar", "title": _("Rides by way of travelling"),
                "subtitle": _("Rides posted in the period; a ride can have several"),
                "labels": [o.label for o in options],
                "series": [{"name": _("Rides"), "data": [counts[o.field] for o in options]}]}

    def _recency(self):
        days = lambda n: self.now - timedelta(days=n)
        counts = self.users.aggregate(
            week=Count("pk", filter=Q(last_login__gte=days(7))),
            month=Count("pk", filter=Q(last_login__gte=days(30), last_login__lt=days(7))),
            quarter=Count("pk", filter=Q(last_login__gte=days(90), last_login__lt=days(30))),
            older=Count("pk", filter=Q(last_login__lt=days(90))),
            never=Count("pk", filter=Q(last_login__isnull=True)),
        )
        labels = [_("Last 7 days"), _("8–30 days ago"), _("31–90 days ago"), _("Over 90 days ago"), _("Never")]
        return {"id": "recency", "kind": "hbar", "title": _("Last login"),
                "subtitle": _("When each user last logged in, counted from today"),
                "labels": labels, "series": [{"name": _("Users"), "data": list(counts.values())}]}

    def _settings(self):
        users = self.users
        total = users.count()
        counts = users.aggregate(
            photo=Count("pk", filter=Q(pfp__isnull=False) & ~Q(pfp="")),
            phone=Count("pk", filter=Q(phone__isnull=False) & ~Q(phone="")),
            show_photo=Count("pk", filter=Q(show_photo=True)),
            share_email=Count("pk", filter=Q(share_email=True)),
            share_phone=Count("pk", filter=Q(share_phone=True)),
            all_emails=Count("pk", filter=Q(email_notifications=User.EmailNotifications.ALL)),
            welcomed=Count("pk", filter=Q(welcomed_at__isnull=False)),
        )
        counts["push"] = users.filter(Exists(PushSubscription.objects.filter(user=OuterRef("pk")))).count()
        labels = {
            "photo": _("Has a profile photo"), "phone": _("Has a phone number"), "show_photo": _("Shows the photo"),
            "share_email": _("Shares the email address"), "share_phone": _("Shares the phone number"),
            "all_emails": _("Gets all notifications by email"), "push": _("Has push notifications on"),
            "welcomed": _("Has seen the welcome popup"),
        }
        return {"id": "settings", "kind": "hbar", "percent": True, "title": _("Profiles and settings"),
                "subtitle": _("Share of users, in per cent"),
                "labels": list(labels.values()),
                "series": [{"name": _("Users"), "data": [_percent(counts[key], total) for key in labels]}]}

    def _name_visibility(self):
        counts = dict(self.users.order_by().values("name_visibility").annotate(n=Count("pk")).values_list("name_visibility", "n"))
        choices = User.NameVisibility
        return {"id": "names", "kind": "hbar", "title": _("Name shown to others"),
                "subtitle": _("What other members see of each user's name"),
                "labels": [choice.label for choice in choices],
                "series": [{"name": _("Users"), "data": [counts.get(choice.value, 0) for choice in choices]}]}

    def top_routes(self, count=10):
        """The routes with the most rides posted: (start, destination, rides)."""
        return list(
            self.rides.order_by()
            .annotate(start_name=KT("start_json__displayName"), destination_name=KT("destination_json__displayName"))
            .values("start_name", "destination_name").annotate(n=Count("pk")).order_by("-n", "start_name")
            .values_list("start_name", "destination_name", "n")[:count]
        )

    # The table of users, and the CSV

    def user_rows(self, sort=DEFAULT_SORT):
        def count(model, user_field, test=None, **filters):
            # test: what is left out, as having to do with the test user or test rides
            counted = model.objects.filter(**{user_field: OuterRef("pk")}, **self._in_period("created_at"), **filters)
            if test is not None:
                counted = counted.exclude(test)
            counted = counted.order_by().values(user_field).annotate(n=Count("pk")).values("n")
            return Coalesce(Subquery(counted, output_field=IntegerField()), 0)

        last_active = (Event.objects.filter(user=OuterRef("pk"), **self._in_period("created_at")).order_by()
                       .values("user").annotate(last=Max("created_at")).values("last"))

        accepted, declined = RideRequest.Status.ACCEPTED, RideRequest.Status.DECLINED
        # Requests to test rides, and (on the user's own rides) from the test user
        requests_test = _test_rides("ride__") | Q(passenger__email__iexact=TEST_USER_EMAIL)
        pushes = (PushSubscription.objects.filter(user=OuterRef("pk")).order_by().values("user")
                  .annotate(n=Count("pk")).values("n"))
        if sort.lstrip("-") not in SORTS:
            sort = DEFAULT_SORT
        return self.users.annotate(
            rides_posted=count(Ride, "driver", _test_rides()),
            requests_made=count(RideRequest, "passenger", requests_test),
            requests_accepted=count(RideRequest, "passenger", requests_test, status=accepted),
            requests_declined=count(RideRequest, "passenger", requests_test, status=declined),
            requests_received=count(RideRequest, "ride__driver", requests_test),
            requests_received_accepted=count(RideRequest, "ride__driver", requests_test, status=accepted),
            notifications_received=count(Notification, "recipient", _test_rides("ride__")),
            notifications_read=count(Notification, "recipient", _test_rides("ride__"), read_at__isnull=False),
            push_devices=Coalesce(Subquery(pushes, output_field=IntegerField()), 0),
            # The activity log has no events of the test user or about test rides
            last_active=Subquery(last_active),
            active_days=count(Event, "user", kind=Kind.ACTIVE),
            searches=count(Event, "user", kind=Kind.SEARCHED),
            rides_viewed=count(Event, "user", kind=Kind.RIDE_VIEWED),
            rides_deleted=count(Event, "user", kind=Kind.RIDE_DELETED),
            requests_withdrawn=count(Event, "user", kind__in=[Kind.REQUEST_WITHDRAWN, Kind.PASSENGER_LEFT]),
        ).order_by(sort, "email")
