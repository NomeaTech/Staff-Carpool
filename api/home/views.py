from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from accounts.privacy import contact_details
from . import notifications
from django.http import HttpResponseRedirect
from test_app.models import Ride, RideRequest, Via
from test_app.routes import build_route, as_route_point
from django.contrib.auth.decorators import login_required
from test_app.models import Ride
from .forms import SearchForm
from .campuses import CAMPUSES
from test_app.forms import RideForm, WEEKDAYS as WEEKDAY_NAMES
import logging
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.db.models import Q, F, Count, Exists, OuterRef, Subquery, ExpressionWrapper, FloatField, BooleanField, Case, When, Value
from django.db.models.functions import Least
from django.db import transaction
from django.core.paginator import Paginator
import os
import requests
from django.views.decorators.cache import never_cache
import json
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance, LineLocatePoint
from django.urls import reverse
from django.http import HttpResponseRedirect, Http404
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
import uuid

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

    recent_rides = (
        upcoming.exclude(driver=user)
        .with_seats_taken()
        .order_by("-created_at")[:4]
    )

    context = {
        "my_rides": my_ride_entries(user, upcoming)[:HOME_RIDES],
        "pending_requests": pending_requests,
        "recent_rides": recent_rides,
    }
    return render(request, "home.html", context)

# How many of the user's upcoming rides the home page shows
HOME_RIDES = 4

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

    context = {
        "ride": ride,
        "is_driver": is_driver,
        # Ride partners see each other's full names and shared contact details
        "is_partner": False,
        "is_upcoming": Ride.objects.upcoming().filter(pk=ride.pk).exists(),
        "vias": ride.via_points.all(),
        "share_url": request.build_absolute_uri(reverse("ride_detail", args=[ride.pk])),
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

    return render(request, "ride_detail.html", context)

@login_required
@require_POST
def request_ride(request, ride_id):
    ride = get_object_or_404(Ride.objects.upcoming().with_seats_taken(), pk=ride_id)
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
            if ride_request.status == RideRequest.Status.ACCEPTED:
                notifications.passenger_left(request, ride_request)
                messages.success(request, _("You have left the ride."))
            else:
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
                notifications.request_answered(request, ride_request)
                messages.success(request, _("Request accepted. You can now see the passenger's shared contact details."))
        elif not accept and ride_request.status != RideRequest.Status.DECLINED:
            ride_request.status = RideRequest.Status.DECLINED
            ride_request.save(update_fields=["status", "updated_at"])
            notifications.request_answered(request, ride_request)
            messages.success(request, _("Request declined."))

    return redirect("ride_detail", ride_id=ride_request.ride_id)

@login_required
@require_POST
def delete_ride(request):
    ride_id = get_ride_id(request)
    # Only deletes the ride if the user is its driver
    ride = Ride.objects.filter(pk=ride_id, driver=request.user).first()
    if ride:
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
    context = {"GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"), "campuses": CAMPUSES}

    # Opening the page shows all rides, the same as searching without filters
    search_form = SearchForm(request.POST if request.method == "POST" else {})
    context["form"] = search_form

    if search_form.is_valid():
        rides = search_rides(search_form.cleaned_data)
        context["page"] = Paginator(rides, SEARCH_PAGE_SIZE).get_page(request.POST.get("page"))
        context["searched"] = True

    # Asynchronous searches from the search page only need the results
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "search_results.html", context)

    return render(request, "search.html", context)

# How far a ride may start or end from the searched start or destination to
# count as a matching ride. Rides further away that pass by on their route are
# shown separately, as rides on the way.
DIRECT_RADIUS = D(km=10)
# How far a ride's route may pass from the searched start or destination to be
# shown as a ride that could pick the searcher up / drop them off on the way
ON_THE_WAY_RADIUS = D(km=5)

def search_rides(form_clean):
    """
    Build the search query. Nothing is fetched until it is evaluated.

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
    rides = Ride.objects.select_related("driver")

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

    if form_clean["offer"]:
        rides = rides.filter(offer=True)
    if form_clean["request"]:
        rides = rides.filter(request=True)
    if form_clean["other"]:
        rides = rides.filter(Q(other=True) | Q(train=True) | Q(bus=True) | Q(taxi=True))
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

    if request.method == "POST":
        ride_form = RideForm(request.POST)
        if ride_form.is_valid():
            try:
                ride = ride_form.save(commit=False)

                # collect vias, in the order they appear on the form
                vias_json = []
                for key, value in request.POST.items():
                    if key.startswith("via_") and key.endswith("_json") and value:
                        vias_json.append(json.loads(value))

                sl = json.loads(request.POST["start_json"])["location"]
                ride.start_location = Point(sl["lng"], sl["lat"], srid=4326)

                dl = json.loads(request.POST["destination_json"])["location"]
                ride.destination_location = Point(dl["lng"], dl["lat"], srid=4326)

                ride.driver = request.user

                with transaction.atomic():
                    ride.save()
                    Via.objects.bulk_create([
                        Via(
                            ride=ride,
                            order=order,
                            via_json=via_json,
                            location=Point(via_json["location"]["lng"], via_json["location"]["lat"], srid=4326),
                        )
                        for order, via_json in enumerate(vias_json[:8])
                    ])

                # Saved separately, so that a failed or slow Routes API
                # request cannot lose the ride itself
                try:
                    ride.route = build_route(ride)
                    ride.save(update_fields=["route"])
                except Exception:
                    logger.exception("Could not save the route of ride %s", ride.pk)
            except Exception:
                logger.exception("Could not save a new ride")
                return add_ride_page(request, ride_form)
            return HttpResponseRedirect(f"/app/ride/{ride.id}")
            # return HttpResponseRedirect("/app/home")

        else:
            return add_ride_page(request, ride_form)
    else:
        # from_address_form = AddressForm()
        # to_address_form = AddressForm()
        ride_form = RideForm()

    return add_ride_page(request, ride_form)


DAY_LABELS = [_("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri"), _("Sat"), _("Sun")]

def add_ride_page(request, ride_form):
    """
    The add ride page. After a failed post, the schedule entered is shown
    again with the errors (see RideForm.clean).
    """
    days = [
        {
            "label": label,
            "key": day,
            "checked": ride_form[f"{day}_check"].value(),
            "leaving": ride_form[f"{day}_leaving_at_time"].value() or "",
            "returning": ride_form[f"{day}_returning_at_time"].value() or "",
        }
        for label, (day, _name) in zip(DAY_LABELS, WEEKDAY_NAMES)
    ]
    context = {
        "ride_form": ride_form,
        "day_list": days,
        "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"), "campuses": CAMPUSES,
    }
    return render(request, "add_ride.html", context)


@login_required
def digitrans_autocomplete_proxy(request):
    q = request.GET.get('text', '').strip()
    if not q:
        return JsonResponse({'features': []})

    size = request.GET.get('size', '7')

    key = os.getenv("DIGITRANS_SUBSCRIPTION_KEY")
    headers = {'Digitransit-subscription-key': key} if key else {}

    try:
        resp = requests.get('https://api.digitransit.fi/geocoding/v1/autocomplete', params={'text': q, 'size': size}, headers=headers, timeout=5)
        return JsonResponse(resp.json(), safe=False)
    except requests.RequestException as e:
        logger.exception('Digitransit proxy request failed')
        return JsonResponse({'features': []}, status=502)