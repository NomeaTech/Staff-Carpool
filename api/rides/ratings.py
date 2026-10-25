"""
Rating co-riders.

After a trip, its driver and each of its accepted passengers are asked to
rate each other out of 10. Passengers do not rate each other: they are not
ride partners and do not see each other's names (accounts/privacy.py).

When
----
A trip can be rated from RATE_AFTER after it (after its return, for a
return trip) for RATING_WINDOW, and a rating can be changed until then. A
one-time ride's trip is its date. A recurring ride is rated once per driver
and passenger, after their first trip together: the first of the
passenger's days after the driver accepted them.

Once a trip can be rated, its ratings are made waiting for an answer
(Rating.Outcome.PENDING), one each way between the driver and each
passenger: by sync() when the member opens the app, and by remind(), which
also tells them (notifications RATE_RIDE). There is no scheduled job:
remind() runs on each member's first visit of the day (activity/middleware.py),
or from the remind_ratings command if a cron job is set up.

If a passenger leaves or is removed, or the ride is deleted, after the trip
has started, its ratings are made first (keep()), so that leaving cannot
avoid them. The ratings page (home.views.ratings) lists them; the ride's
page too while it exists.

Answers
-------
A score with what went well (Rating.Tag), or that the co-rider did not
show up, or no rating; or that the ride did not take place, for all of
them. A comment can be added for the admins only.

When the two co-riders' answers disagree (disagree()), e.g. one says the
other did not show up and the other rated them, both are disputed and do
not count until the admins decide in the admin (Rating.Review).

What others see
---------------
Ratings are anonymous: members only see a member's average score and most
ticked tags, and only once RATING_MIN_COUNT ratings count ("Not rated yet"
before). Once NO_SHOW_SHOWN co-riders have said a member did not show up
within NO_SHOW_PERIOD, it is shown with their rating, and they are warned
(notifications NO_SHOW_WARNING).
"""
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import WEEKDAY_KEYS, Rating, RideRequest

RATE_AFTER = timedelta(hours=2)
RATING_WINDOW = timedelta(days=30)
# How many ratings a member needs before their average is shown
RATING_MIN_COUNT = 3
SCORES = range(1, 11)
# How many co-riders must have said a member did not show up, and within
# how long, for it to be shown
NO_SHOW_SHOWN = 2
NO_SHOW_PERIOD = timedelta(days=365)
# How many of a member's most ticked tags are shown
TOP_TAGS = 3


@dataclass
class Trip:
    """The trip a driver and passenger rate each other on."""
    date: date
    starts_at: datetime
    # When it can be rated from
    due_at: datetime


@dataclass
class TripRatings:
    """The user's ratings of their co-riders on one trip, for one rating form."""
    ride: object
    route: str
    trip_date: date
    ratings: list

    @property
    def pending(self):
        return any(rating.outcome == Rating.Outcome.PENDING for rating in self.ratings)

    @property
    def deadline(self):
        return min(rating.due_at for rating in self.ratings) + RATING_WINDOW

    @property
    def rates_driver(self):
        return any(rating.rated_is_driver for rating in self.ratings)


@dataclass
class Summary:
    """A member's ratings that count: how many, their average score, most ticked tags and no-shows."""
    count: int = 0
    average: float | None = None
    # (label, how many ticked it), most ticked first
    tags: tuple = ()
    no_shows: int = 0

    @property
    def public(self):
        return self.count >= RATING_MIN_COUNT

    @property
    def shows_no_shows(self):
        return self.no_shows >= NO_SHOW_SHOWN


def trip(ride_request):
    """The trip ride_request's driver and passenger rate each other on, or None, e.g. a recurring ride with no days."""
    ride = ride_request.ride
    if ride.one_time:
        leaving = ride.leaving_at()
        if leaving is None:
            return None
        return Trip(leaving.date(), aware(leaving), aware(max(ride.returning_at() or leaving, leaving)) + RATE_AFTER)

    accepted = timezone.localtime(ride_request.accepted_at or ride_request.updated_at).replace(tzinfo=None)
    days = ride_request.ride_days()
    # Within a week from the day accepted, that day included again in case
    # the ride had already left on it
    for offset in range(8):
        day = accepted.date() + timedelta(days=offset)
        key = WEEKDAY_KEYS[day.weekday()]
        if key not in days:
            continue
        leaving, returning = (at_time(day, value) for value in ride.times_on(key))
        if leaving is None or leaving < accepted:
            continue
        return Trip(day, aware(leaving), aware(max(returning or leaving, leaving)) + RATE_AFTER)
    return None


def at_time(day, value):
    """A recurring ride's time (Ride.times_on) on day, None if it has none."""
    return datetime.combine(day, value) if value else None


def aware(local):
    return timezone.make_aware(local)


def can_be_rated(when, now):
    return when.due_at <= now < when.due_at + RATING_WINDOW


def recent_requests(now):
    """
    The accepted requests that can have a trip to rate. Dates are stored as
    datetime-local strings (Ride.leaving_at_date_time), with returns given
    a week.
    """
    since = now - RATING_WINDOW - timedelta(days=8)
    return RideRequest.objects.filter(status=RideRequest.Status.ACCEPTED).filter(
        Q(ride__one_time=True, ride__leaving_at_date_time__gte=timezone.localtime(since).strftime("%Y-%m-%dT%H:%M"))
        | Q(ride__one_time=False, accepted_at__gte=since)
    ).select_related("ride__driver", "passenger")


def make(trips, rater=None, reminded=False):
    """
    Makes the ratings waiting for an answer that do not exist yet, for each
    (ride_request, Trip) in trips: both ways, or only by rater. Returns the
    ones made.
    """
    wanted = []
    for ride_request, when in trips:
        ride = ride_request.ride
        for by, of, of_driver in ((ride.driver, ride_request.passenger, False), (ride_request.passenger, ride.driver, True)):
            if rater is None or by.pk == rater.pk:
                wanted.append(Rating(
                    ride=ride, route=ride.route_name(), rater=by, rated=of, rated_is_driver=of_driver,
                    trip_date=when.date, due_at=when.due_at, reminded=reminded,
                ))
    if not wanted:
        return []
    existing = set(
        Rating.objects.filter(ride__in={rating.ride for rating in wanted}).values_list("ride", "rater", "rated")
    )
    new = [rating for rating in wanted if (rating.ride.pk, rating.rater.pk, rating.rated.pk) not in existing]
    # Made at the same time elsewhere: left as they are
    Rating.objects.bulk_create(new, ignore_conflicts=True)
    return new


def sync(user, now=None):
    """Makes the ratings user can give now, of their co-riders on accepted requests."""
    now = now or timezone.now()
    requests = recent_requests(now).filter(Q(passenger=user) | Q(ride__driver=user))
    trips = [(ride_request, when) for ride_request in requests if (when := trip(ride_request)) and can_be_rated(when, now)]
    # The user is in the app, where they are shown
    make(trips, rater=user, reminded=True)


def keep(ride_requests, now=None):
    """
    Before passengers stop being passengers (they leave, are removed, or
    the ride is deleted): makes the ratings of trips that have started.
    """
    now = now or timezone.now()
    trips = []
    for ride_request in ride_requests:
        if ride_request.status != RideRequest.Status.ACCEPTED:
            continue
        when = trip(ride_request)
        if when and when.starts_at <= now < when.due_at + RATING_WINDOW:
            trips.append((ride_request, when))
    make(trips)


def remind(request=None, now=None):
    """
    Makes the ratings that can be given now and tells the raters who have
    not been told: one notification for each of their trips.
    """
    from notifications import services as notifications
    now = now or timezone.now()
    make([(ride_request, when) for ride_request in recent_requests(now)
          if (when := trip(ride_request)) and can_be_rated(when, now)])

    waiting = Rating.objects.filter(
        outcome=Rating.Outcome.PENDING, reminded=False, due_at__lte=now, due_at__gt=now - RATING_WINDOW,
    ).select_related("ride", "rater")
    told = set()
    with transaction.atomic():
        for rating in waiting:
            key = (rating.rater_id, rating.ride_id or rating.route, rating.trip_date)
            if key not in told:
                told.add(key)
                notifications.send(request, rating.rater, notifications.Kind.RATE_RIDE, rating.ride, route=rating.route)
        waiting.update(reminded=True)
    return len(told)


def trips_to_rate(user, ride=None, now=None):
    """
    The trips user can rate now, or change their ratings of, as
    [TripRatings]: of ride, or of all their rides. Oldest first.
    """
    now = now or timezone.now()
    sync(user, now)
    ratings = Rating.objects.filter(
        rater=user, due_at__lte=now, due_at__gt=now - RATING_WINDOW,
    ).select_related("ride", "rated").order_by("due_at", "-rated_is_driver", "rated__first_name")
    if ride is not None:
        ratings = ratings.filter(ride=ride)
    trips = {}
    for rating in ratings:
        key = (rating.ride_id or rating.route, rating.trip_date)
        trips.setdefault(key, TripRatings(rating.ride, rating.route, rating.trip_date, [])).ratings.append(rating)
    return list(trips.values())


def save(user, answers):
    """
    Saves user's answers, as [(Rating, outcome, score, tags, comment)], and
    looks for disputes and no-shows. Returns how many of each outcome there were.
    """
    no_shows = []
    with transaction.atomic():
        for rating, outcome, score, tags, comment in answers:
            if (rating.outcome, rating.score) != (outcome, score):
                # A changed answer is looked at again
                rating.review = Rating.Review.NONE
            rating.outcome, rating.score, rating.tags, rating.comment = outcome, score, tags, comment
            rating.save(update_fields=["outcome", "score", "tags", "comment", "review", "updated_at"])
            update_dispute(rating)
            if outcome == Rating.Outcome.NO_SHOW:
                no_shows.append(rating.rated)
    for member in no_shows:
        warn_if_no_shows(member)
    outcomes = [outcome for _rating, outcome, *_rest in answers]
    return {outcome.value: outcomes.count(outcome) for outcome in Rating.Outcome if outcome != Rating.Outcome.PENDING}


# Answers saying the rated co-rider did not take part in the trip, and ones
# saying the rater did
SAYS_ABSENT = {Rating.Outcome.NO_SHOW, Rating.Outcome.NOT_HAPPENED}
SAYS_THERE = {Rating.Outcome.RATED, Rating.Outcome.NO_SHOW}


def disagree(outcome, other):
    """
    Whether two co-riders' answers about each other disagree: one says the
    other was not there, or that the ride did not happen, and the other
    says they were there themselves (rated them, or says they did not show up).
    """
    return (outcome in SAYS_ABSENT and other in SAYS_THERE) or (other in SAYS_ABSENT and outcome in SAYS_THERE)


def update_dispute(rating):
    """Marks rating and the co-rider's rating of the rater disputed when they disagree, and not when they no longer do."""
    reverse = Rating.objects.filter(rater=rating.rated_id, rated=rating.rater_id, trip_date=rating.trip_date)
    reverse = reverse.filter(ride=rating.ride_id) if rating.ride_id else reverse.filter(ride=None, route=rating.route)
    other = reverse.first()
    disputed = other is not None and disagree(rating.outcome, other.outcome)
    for each in filter(None, (rating, other)):
        if disputed and each.review == Rating.Review.NONE:
            each.review = Rating.Review.PENDING
        elif not disputed and each.review == Rating.Review.PENDING:
            each.review = Rating.Review.NONE
        else:
            continue
        each.save(update_fields=["review", "updated_at"])


def counted(ratings):
    """The ratings that count: not disputed, or counted after review."""
    return ratings.exclude(review__in=[Rating.Review.PENDING, Rating.Review.DISCARDED])


def no_show_count(member, today=None):
    """How many co-riders have said member did not show up, within NO_SHOW_PERIOD."""
    today = today or timezone.localdate()
    return counted(Rating.objects.filter(
        rated=member, outcome=Rating.Outcome.NO_SHOW, trip_date__gte=today - NO_SHOW_PERIOD,
    )).values("rater").distinct().count()


def warn_if_no_shows(member, request=None):
    """Warns member, once within NO_SHOW_PERIOD, when their no-shows start being shown."""
    from notifications import services as notifications
    from notifications.models import Notification
    if no_show_count(member) < NO_SHOW_SHOWN:
        return
    since = timezone.now() - NO_SHOW_PERIOD
    if Notification.objects.filter(recipient=member, kind=notifications.Kind.NO_SHOW_WARNING, created_at__gte=since).exists():
        return
    notifications.send(request, member, notifications.Kind.NO_SHOW_WARNING)


def summaries(users, today=None):
    """Each user's Summary, by their pk."""
    today = today or timezone.localdate()
    ratings = counted(Rating.objects.filter(rated__in=users))
    scored = ratings.filter(outcome=Rating.Outcome.RATED)

    rows = {
        row["rated"]: row
        for row in scored.values("rated").annotate(count=Count("pk"), average=Avg("score"))
    }
    tags = {}
    for rated, ticked in scored.exclude(tags=[]).values_list("rated", "tags"):
        tags.setdefault(rated, Counter()).update(ticked)
    no_shows = dict(
        ratings.filter(outcome=Rating.Outcome.NO_SHOW, trip_date__gte=today - NO_SHOW_PERIOD)
        .values("rated").annotate(n=Count("rater", distinct=True)).values_list("rated", "n")
    )

    found = {}
    for user in users:
        row = rows.get(user.pk, {"count": 0, "average": None})
        top = tags.get(user.pk, Counter()).most_common(TOP_TAGS)
        found[user.pk] = Summary(
            row["count"], row["average"],
            tuple((Rating.Tag(tag).label, n) for tag, n in top if tag in Rating.Tag.values),
            no_shows.get(user.pk, 0),
        )
    return found
