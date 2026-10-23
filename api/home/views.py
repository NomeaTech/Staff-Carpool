from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from accounts.privacy import contact_details
from notifications import services as notifications
from notifications.models import Notification
from django.http import HttpResponseRedirect
from rides.models import Ride, RideRequest, Via
from rides.routes import build_route, as_route_point
from rides.transport import TRANSPORT_OPTIONS, icon_layout
from django.contrib.auth.decorators import login_required
from .forms import SearchForm
from .campuses import CAMPUSES
from rides.forms import RideForm, WEEKDAYS as WEEKDAY_NAMES, clean_place
import logging
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.db.models import Q, F, Count, Exists, OuterRef, Subquery, ExpressionWrapper, FloatField, BooleanField, Case, When, Value
from django.db.models.functions import Least
from django.db import transaction
from django.core.paginator import Paginator
import os
import operator
from functools import reduce
import requests
from django.views.decorators.cache import never_cache
import json
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance, LineLocatePoint
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect, Http404
from accounts.models import User
from activity import events
from activity.models import Event, Kind
from datetime import datetime, time, timedelta
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
import uuid
from django.utils import timezone

logger = logging.getLogger(__name__)

@login_required
def index(request):
    return HttpResponseRedirect("/app/home/")

@login_required
def home(request):
    user = request.user
    upcoming = Ride.objects.upcoming()

    pending_requests = RideRequest.objects.filter(
        ride__in=upcoming, ride__driver=user, status=RideRequest.Status.PENDING
    ).select_related("ride", "passenger")

    # Rides posted to groups are shown with the user's groups instead
    recent_rides = (
        upcoming.visible_to(user).exclude(driver=user).filter(groups_only=False)
        .with_seats_taken()
        .order_by("-created_at")[:4]
    )

    context = {
        "my_rides": my_ride_entries(user, upcoming)[:HOME_RIDES],
        "pending_requests": pending_requests,
        "recent_rides": recent_rides,
        "show_welcome": user.welcomed_at is None,
        **group_summary(user, upcoming),
    }
    return render(request, "home.html", context)

# How many rides in the user's groups the home page shows
HOME_GROUP_RIDES = 5
# Without an earlier visit, rides posted this long ago count as new
NEW_WITHOUT_VISIT = timedelta(days=7)

def group_summary(user, upcoming):
    """
    The home page's groups section: the user's groups, each with the rides
    posted to it since the user's last visit (and, for admins, the requests
    to join waiting), and the latest upcoming rides others posted to them.
    """
    from groups.models import Membership
    memberships = list(Membership.objects.active().filter(user=user).select_related("group").order_by("group__name"))
    if not memberships:
        return {"group_memberships": []}
    # The user's last visit before today (activity/middleware.py)
    today = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    last_visit = (Event.objects.filter(user=user, kind=Kind.ACTIVE, created_at__lt=today)
                  .order_by("-created_at").values_list("created_at", flat=True).first())
    new_since = last_visit or timezone.now() - NEW_WITHOUT_VISIT

    group_ids = {m.group_id for m in memberships}
    in_my_groups = Ride.groups.through.objects.filter(ride=OuterRef("pk"), group__in=group_ids)
    rides = list(
        upcoming.filter(Exists(in_my_groups)).exclude(driver=user).select_related("driver")
        .prefetch_related("groups").with_seats_taken().order_by("-created_at")
    )
    new_counts = {}
    for ride in rides:
        ride.is_new = ride.created_at > new_since
        # Only the user's own groups are named
        ride.my_groups = [group for group in ride.groups.all() if group.pk in group_ids]
        for group in ride.my_groups:
            new_counts[group.pk] = new_counts.get(group.pk, 0) + ride.is_new

    waiting = dict(
        Membership.objects.pending().filter(group__in=[m.group_id for m in memberships if m.is_admin])
        .values("group").annotate(n=Count("pk")).values_list("group", "n")
    )
    for membership in memberships:
        membership.new_rides = new_counts.get(membership.group_id, 0)
        membership.waiting = waiting.get(membership.group_id, 0)
    return {
        "group_memberships": memberships,
        "group_rides": rides[:HOME_GROUP_RIDES],
        "group_rides_more": len(rides) > HOME_GROUP_RIDES,
        "new_group_rides": sum(ride.is_new for ride in rides),
    }

@login_required
@require_POST
def welcomed(request):
    """The welcome popup was shown (home.html), so it does not open again."""
    if User.objects.filter(pk=request.user.pk, welcomed_at=None).update(welcomed_at=timezone.now()):
        events.record(Kind.WELCOMED, request.user)
    return HttpResponse(status=204)

# How many of the user's upcoming rides the home page shows
HOME_RIDES = 4

@login_required
def more(request):
    """The More tab of the mobile dock: account, settings and help (the navbar's profile picture on desktop)."""
    return render(request, "more.html")

@login_required
def my_rides(request):
    rides = Ride.objects.all()
    context = {
        "upcoming": my_ride_entries(request.user, rides.upcoming()),
        "past": my_ride_entries(request.user, rides.past(), reverse=True),
    }
    return render(request, "my_rides.html", context)

def my_ride_entries(user, rides, reverse=False):
    """
    The rides among rides that the user drives or has requested to join, as
    (ride, request) pairs, request being None for rides the user drives.
    One-time rides come in the order they leave, then recurring rides.
    """
    driving = rides.filter(driver=user).with_seats_taken().annotate(
        pending=Count("requests", filter=Q(requests__status=RideRequest.Status.PENDING))
    )
    requested = RideRequest.objects.filter(ride__in=rides, passenger=user).select_related("ride")

    entries = [(ride, None) for ride in driving] + [(r.ride, r) for r in requested]
    dated = sorted((e for e in entries if e[0].leaving_at()), key=lambda e: e[0].leaving_at(), reverse=reverse)
    return dated + [e for e in entries if not e[0].leaving_at()]

# Everything to do with recurring rides should be moved to its own app
@login_required
def ride_detail(request, ride_id):
    ride = get_object_or_404(Ride.objects.select_related("driver").with_seats_taken(), pk=ride_id)
    user = request.user
    is_driver = ride.driver_id == user.id

    # A ride posted to groups the user is not in (e.g. from a shared link):
    # say which groups to join, without showing the ride
    if not Ride.objects.visible_to(user).filter(pk=ride.pk).exists():
        return render(request, "ride_not_shown.html", {"groups": ride.groups.all()}, status=403)

    # Seeing the ride is seeing what its notifications were about. A page
    # loaded early by Turbo (when a link is hovered or touched) may never be
    # seen: it marks them read itself once shown (ride_detail.html).
    unread = Notification.objects.filter(recipient=user, ride=ride, read_at__isnull=True)
    loaded_early = request.headers.get("X-Sec-Purpose") == "prefetch"
    mark_read_when_shown = loaded_early and unread.exists()
    if not loaded_early:
        unread.update(read_at=timezone.now())

    context = {
        "ride": ride,
        "is_driver": is_driver,
        # Ride partners see each other's full names and shared contact details
        "is_partner": False,
        "is_upcoming": Ride.objects.upcoming().filter(pk=ride.pk).exists(),
        "vias": ride.via_points.all(),
        "share_url": request.build_absolute_uri(reverse("ride_detail", args=[ride.pk])),
        "mark_read_when_shown": mark_read_when_shown,
        "ride_groups": ride.groups.all() if ride.groups_only else None,
    }

    if is_driver:
        # Accepted passengers are the driver's ride partners: their full names
        # and shared contact details are shown (see accounts/privacy.py)
        requests = ride.requests.exclude(status=RideRequest.Status.DECLINED).select_related("passenger")
        context["pending_requests"] = [r for r in requests if r.status == RideRequest.Status.PENDING]
        context["passengers"] = [
            (r, contact_details(r.passenger)) for r in requests if r.status == RideRequest.Status.ACCEPTED
        ]
    else:
        own_request = ride.requests.filter(passenger=user).first()
        context["own_request"] = own_request
        context["is_partner"] = own_request is not None and own_request.status == RideRequest.Status.ACCEPTED
        if context["is_partner"]:
            context["driver_contacts"] = contact_details(ride.driver)

    if not loaded_early:
        if is_driver:
            role = "driver"
        elif context["is_partner"]:
            role = "passenger"
        else:
            role = "requested" if context["own_request"] else "other"
        events.record(Kind.RIDE_VIEWED, user, ride, role=role)

    return render(request, "ride_detail.html", context)

@login_required
@require_POST
def request_ride(request, ride_id):
    ride = get_object_or_404(Ride.objects.upcoming().visible_to(request.user).with_seats_taken(), pk=ride_id)
    message = request.POST.get("message", "").strip()[:500]

    if ride.driver_id == request.user.id:
        messages.error(request, _("You cannot request to join your own ride."))
    elif ride.is_full():
        messages.error(request, _("This ride has no free seats left."))
    else:
        try:
            with transaction.atomic():
                ride_request = RideRequest.objects.create(ride=ride, passenger=request.user, message=message)
                notifications.request_received(request, ride_request)
            events.record(Kind.REQUEST_SENT, request.user, ride, message=bool(message), seats_left=ride.seats_left())
            messages.success(request, _("Request sent. You will be notified when the driver responds."))
        except IntegrityError:
            # The user has already requested to join this ride
            pass

    return redirect("ride_detail", ride_id=ride_id)

@login_required
@require_POST
def withdraw_request(request, ride_id):
    """Withdraws a pending request, or leaves the ride once it was accepted."""
    with transaction.atomic():
        ride_request = RideRequest.objects.filter(
            ride=ride_id, passenger=request.user
        ).exclude(status=RideRequest.Status.DECLINED).select_related("ride").first()

        if ride_request:
            ride_request.delete()
            hours = events.hours_since(ride_request.created_at)
            if ride_request.status == RideRequest.Status.ACCEPTED:
                notifications.passenger_left(request, ride_request)
                events.record(Kind.PASSENGER_LEFT, request.user, ride_request.ride, hours=hours)
                messages.success(request, _("You have left the ride."))
            else:
                notifications.request_withdrawn(request, ride_request)
                events.record(Kind.REQUEST_WITHDRAWN, request.user, ride_request.ride, hours=hours)
                messages.success(request, _("Your request was withdrawn."))

    return redirect("ride_detail", ride_id=ride_id)

@login_required
@require_POST
def answer_request(request, request_id):
    """The driver accepts or declines a request, or removes an accepted passenger."""
    accept = request.POST.get("action") == "accept"

    with transaction.atomic():
        ride_request = get_object_or_404(
            RideRequest.objects.select_related("ride", "passenger"),
            pk=request_id, ride__driver=request.user,
        )
        # Locking the ride makes requests accepted at the same time count
        # each other's seats
        ride = Ride.objects.select_for_update().get(pk=ride_request.ride_id)

        if accept and ride_request.status == RideRequest.Status.PENDING:
            if ride.is_full():
                messages.error(request, _("The ride is full. Increase its seats or remove a passenger first."))
            else:
                ride_request.status = RideRequest.Status.ACCEPTED
                ride_request.save(update_fields=["status", "updated_at"])
                notifications.request_accepted(request, ride_request)
                events.record(Kind.REQUEST_ACCEPTED, request.user, ride, hours=events.hours_since(ride_request.created_at))
                messages.success(request, _("Request accepted. You can now see the passenger's shared contact details."))
        elif not accept and ride_request.status != RideRequest.Status.DECLINED:
            # Declining a request, or removing a passenger who was accepted
            was_accepted = ride_request.status == RideRequest.Status.ACCEPTED
            ride_request.status = RideRequest.Status.DECLINED
            ride_request.save(update_fields=["status", "updated_at"])
            kind = Kind.PASSENGER_REMOVED if was_accepted else Kind.REQUEST_DECLINED
            events.record(kind, request.user, ride, hours=events.hours_since(ride_request.created_at))
            if was_accepted:
                notifications.passenger_removed(request, ride_request)
                messages.success(request, _("The passenger was removed from the ride."))
            else:
                notifications.request_declined(request, ride_request)
                messages.success(request, _("Request declined."))

    return redirect("ride_detail", ride_id=ride_request.ride_id)

@login_required
@require_POST
def delete_ride(request):
    ride_id = get_ride_id(request)
    # Only deletes the ride if the user is its driver
    ride = Ride.objects.filter(pk=ride_id, driver=request.user).first()
    if ride:
        statuses = list(ride.requests.values_list("status", flat=True))
        events.record(
            Kind.RIDE_DELETED, request.user, ride,
            passengers=statuses.count(RideRequest.Status.ACCEPTED),
            pending=statuses.count(RideRequest.Status.PENDING),
            upcoming=Ride.objects.upcoming().filter(pk=ride.pk).exists(),
            hours_old=events.hours_since(ride.created_at),
        )
        with transaction.atomic():
            notifications.ride_cancelled(request, ride)
            ride.delete()
        messages.success(request, _("The ride was deleted."))

    return HttpResponseRedirect(reverse("home"))

def get_ride_id(request):
    try:
        return uuid.UUID(request.POST.get("ride"))
    except (TypeError, ValueError, AttributeError):
        raise Http404


SEARCH_PAGE_SIZE = 12

@login_required
@never_cache
def search(request):
    context = {
        "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"), "campuses": CAMPUSES,
        # The filters' icons and colours, by field
        "transport": {option.field: option for option in TRANSPORT_OPTIONS},
    }

    # Opening the page shows all rides, the same as searching without filters
    search_form = SearchForm(request.POST if request.method == "POST" else {})
    context["form"] = search_form

    if search_form.is_valid():
        rides = search_rides(search_form.cleaned_data, request.user)
        page = Paginator(rides, SEARCH_PAGE_SIZE).get_page(request.POST.get("page"))
        # The icons of the options the search is filtered by come first
        filters = transport_filters(search_form.cleaned_data)
        for ride in page:
            ride.icons = icon_layout(ride.transport_options(), filters)
        context["page"] = page
        context["searched"] = True
        # Searches, not opening the page or changing the page of results
        if request.method == "POST" and "page" not in request.POST:
            record_search(request.user, search_form.cleaned_data, page.paginator)

    # Asynchronous searches from the search page only need the results
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "search_results.html", context)

    return render(request, "search.html", context)

def record_search(user, form_clean, paginator):
    """Records what kind of search it was and how many rides it found, not the places."""
    on_the_way = paginator.object_list.filter(on_the_way=True).count() if paginator.count else 0
    events.record(
        Kind.SEARCHED, user,
        results=paginator.count,
        on_the_way=on_the_way,
        start=bool(form_clean["start_json"]),
        destination=bool(form_clean["destination_json"]),
        date=bool(form_clean["date"]),
        start_campus=events.campus(form_clean["start_json"]),
        destination_campus=events.campus(form_clean["destination_json"]),
        transport=transport_filters(form_clean),
    )

def transport_filters(form_clean):
    """The ways of travelling (Ride fields) ticked in the search form."""
    return [option.field for option in TRANSPORT_OPTIONS if form_clean.get(option.field)]

# How far a ride may start or end from the searched start or destination to
# count as a matching ride. Rides further away that pass by on their route are
# shown separately, as rides on the way.
DIRECT_RADIUS = D(km=10)
# How far a ride's route may pass from the searched start or destination to be
# shown as a ride that could pick the searcher up / drop them off on the way
ON_THE_WAY_RADIUS = D(km=5)

def search_rides(form_clean, user):
    """
    Build the search query, of the rides user may see (groups/models.py).
    Nothing is fetched until it is evaluated.

    Each ride is annotated with on_the_way:
    - False: the ride starts near the searched start and ends near the searched
      destination (or passes it on a via).
    - True: otherwise, the ride's route passes near the searched start and
      destination, in that order. The searcher would have to ask the driver
      to pick them up or drop them off on the way.
    Rides that are not on the way come first.
    """
    start_json = form_clean["start_json"]
    destination_json = form_clean["destination_json"]

    direct = Q()
    on_the_way = Q(route__isnull=False)
    # Distance terms that are added together to order the results
    direct_distances = []
    route_distances = []
    # Rides that have already left (Ride.objects.upcoming) are not shown
    rides = Ride.objects.upcoming().visible_to(user).select_related("driver")

    if start_json:
        sl = start_json["location"]
        start_location = Point(sl["lng"], sl["lat"], srid=4326)
        start_on_route = as_route_point(start_location)

        direct &= Q(start_location__dwithin=(start_location, DIRECT_RADIUS))
        on_the_way &= Q(route__dwithin=(start_on_route, ON_THE_WAY_RADIUS))
        direct_distances.append(Distance("start_location", start_location))
        route_distances.append(Distance("route", start_on_route))

    if destination_json:
        dl = destination_json["location"]
        destination_location = Point(dl["lng"], dl["lat"], srid=4326)
        destination_on_route = as_route_point(destination_location)

        # Match rides that end near the destination or pass by it on a via
        vias_near = Via.objects.filter(
            ride=OuterRef("pk"),
            location__dwithin=(destination_location, DIRECT_RADIUS),
        )
        closest_via = Via.objects.filter(
            ride=OuterRef("pk")
        ).annotate(
            d=Distance("location", destination_location)
        ).order_by("d").values("d")[:1]

        direct &= (
            Q(destination_location__dwithin=(destination_location, DIRECT_RADIUS)) |
            Exists(vias_near)
        )
        on_the_way &= Q(route__dwithin=(destination_on_route, ON_THE_WAY_RADIUS))
        direct_distances.append(Least(
            Distance("destination_location", destination_location),
            Subquery(closest_via),
            output_field=FloatField(),
        ))
        route_distances.append(Distance("route", destination_on_route))

    if start_json and destination_json:
        # The ride must reach the start before the destination. A ride that
        # also returns covers the other direction on the way back.
        rides = rides.annotate(
            start_position=LineLocatePoint("route", start_on_route),
            destination_position=LineLocatePoint("route", destination_on_route),
        )
        on_the_way &= Q(start_position__lt=F("destination_position")) | Q(one_way=False)

    # Rides with any of the ticked ways of travelling
    filters = transport_filters(form_clean)
    if filters:
        rides = rides.filter(reduce(operator.or_, (Q(**{field: True}) for field in filters)))
    if form_clean["date"]:
        rides = rides.filter(on_date(form_clean["date"]))

    # The order must be stable, so that pages do not overlap
    if not (start_json or destination_json):
        return rides.annotate(on_the_way=Value(False)).order_by("-created_at", "-pk")

    total = lambda terms: ExpressionWrapper(sum(terms[1:], terms[0]), output_field=FloatField())
    return rides.filter(direct | on_the_way).annotate(
        on_the_way=Case(When(direct, then=Value(False)), default=Value(True), output_field=BooleanField()),
        dist=Case(
            When(direct, then=total(direct_distances)),
            default=total(route_distances),
            output_field=FloatField(),
        ),
    ).order_by("on_the_way", "dist", "-created_at", "-pk")

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

def on_date(date):
    """
    Match rides happening on the given date:
    - one-time rides leaving on it, or returning on it if they return
    - recurring rides on its day of the week
    """
    # Dates are stored as datetime-local strings, e.g. "2026-10-12T08:30"
    day = date.isoformat()
    one_time = Q(leaving_at_date_time__startswith=day) | Q(one_way=False, returning_at_date_time__startswith=day)
    recurring = Q(**{f"{WEEKDAYS[date.weekday()]}_check": True})
    return Q(one_time=True) & one_time | Q(one_time=False) & recurring

@login_required
def add_ride(request):
    return ride_form_page(request, Ride(driver=request.user))

@login_required
def edit_ride(request, ride_id):
    # Only the ride's driver can edit it
    ride = get_object_or_404(Ride, pk=ride_id, driver=request.user)
    return ride_form_page(request, ride)

def ride_form_page(request, ride):
    """
    The add and edit ride page. Both use RideForm, so a ride is checked the
    same way however it is saved.
    """
    # (A new ride already has its UUID, so ride.pk does not tell them apart)
    editing = not ride._state.adding
    if request.method != "POST":
        # ?audience=groups: offering a ride from the home page's groups section
        initial = {"audience": "groups"} if not editing and request.GET.get("audience") == "groups" else {}
        return render_ride_form(request, RideForm(instance=ride, initial=initial), ride)

    # Before checking the form, which copies the posted values onto the ride
    old_places = place_signature(ride) if editing else None
    ride_form = RideForm(request.POST, instance=ride)
    if not ride_form.is_valid():
        return render_ride_form(request, ride_form, ride)

    try:
        ride = save_ride(ride_form)
    except Exception:
        logger.exception("Could not save ride %s", ride.pk)
        messages.error(request, _("The ride could not be saved. Please try again."))
        return render_ride_form(request, ride_form, ride)

    # Saved separately, so that a failed or slow Routes API request cannot
    # lose the ride itself. Only needed when the places have changed.
    if place_signature(ride) != old_places:
        try:
            ride.route = build_route(ride)
            ride.save(update_fields=["route"])
        except Exception:
            logger.exception("Could not save the route of ride %s", ride.pk)

    if editing:
        if ride_form.has_changed() or place_signature(ride) != old_places:
            notifications.ride_updated(request, ride)
            events.record(Kind.RIDE_EDITED, request.user, ride, places=place_signature(ride) != old_places)
        messages.success(request, _("The ride was updated."))
    else:
        events.record(Kind.RIDE_POSTED, request.user, ride, **events.ride_details(ride))
    return redirect("ride_detail", ride_id=ride.pk)

def save_ride(ride_form):
    """Saves the ride, its locations and its stops on the way (RideForm.clean_vias)."""
    ride = ride_form.save(commit=False)
    point = lambda place: Point(place["location"]["lng"], place["location"]["lat"], srid=4326)
    ride.start_location = point(ride.start_json)
    ride.destination_location = point(ride.destination_json)

    with transaction.atomic():
        ride.save()
        ride_form.save_m2m()
        ride.via_points.all().delete()
        Via.objects.bulk_create([
            Via(ride=ride, order=order, via_json=via, location=point(via))
            for order, via in enumerate(ride_form.cleaned_data["vias"])
        ])
    return ride

def place_signature(ride):
    """The ride's start, stops and destination, to tell whether its route needs recalculating."""
    places = [ride.start_json, *(via.via_json for via in ride.via_points.all()), ride.destination_json]
    return [(place["location"]["lat"], place["location"]["lng"]) for place in places]

def render_ride_form(request, ride_form, ride):
    """
    The add or edit ride page. The places and schedule shown are the ones
    posted after a failed post, otherwise the ride's own (when editing).
    """
    days = [
        {
            "label": label,
            "key": day,
            "checked": ride_form[f"{day}_check"].value(),
            "leaving": ride_form[f"{day}_leaving_at_time"].value() or "",
            "returning": ride_form[f"{day}_returning_at_time"].value() or "",
        }
        for day, label in WEEKDAY_NAMES
    ]
    context = {
        "ride_form": ride_form,
        "ride": ride,
        "editing": not ride._state.adding,
        "day_list": days,
        "initial_places": initial_places(ride_form, ride),
        # The transport choices' icons and colours, by field
        "transport": {option.field: option for option in TRANSPORT_OPTIONS},
        "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"), "campuses": CAMPUSES,
    }
    return render(request, "add_ride.html", context)

def initial_places(ride_form, ride):
    """The start, destination and stops the location pickers start with."""
    def place(value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return None
        return clean_place(value)

    if ride_form.is_bound:
        vias = [place(value) for key, value in ride_form.data.items() if key.startswith("via_") and key.endswith("_json")]
        return {
            "start": place(ride_form.data.get("start_json")),
            "destination": place(ride_form.data.get("destination_json")),
            "vias": [via for via in vias if via],
        }
    if not ride._state.adding:
        return {
            "start": ride.start_json,
            "destination": ride.destination_json,
            "vias": [via.via_json for via in ride.via_points.all()],
        }
    return None


@login_required
def digitrans_autocomplete_proxy(request):
    q = request.GET.get('text', '').strip()
    if not q:
        return JsonResponse({'features': []})

    # Passed on to Digitransit, so only a sensible number of suggestions
    try:
        size = min(max(int(request.GET.get('size', 7)), 1), 20)
    except ValueError:
        size = 7
    q = q[:200]

    key = os.getenv("DIGITRANS_SUBSCRIPTION_KEY")
    headers = {'Digitransit-subscription-key': key} if key else {}

    try:
        resp = requests.get('https://api.digitransit.fi/geocoding/v1/autocomplete', params={'text': q, 'size': size}, headers=headers, timeout=5)
        return JsonResponse(resp.json(), safe=False)
    except requests.RequestException as e:
        logger.exception('Digitransit proxy request failed')
        return JsonResponse({'features': []}, status=502)