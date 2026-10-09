from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from test_app.models import Ride, Via
from test_app.routes import build_route, as_route_point
from django.contrib.auth.decorators import login_required
from test_app.models import Ride
from .forms import SearchForm
from .campuses import CAMPUSES
from accounts.models import User
from test_app.forms import RideForm
import logging
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.db.models import Q, F, Exists, OuterRef, Subquery, ExpressionWrapper, FloatField, BooleanField, Case, When, Value
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

    rides_created = Ride.objects.filter(driver=user.pk)
    rides_registered = Ride.objects.filter(passenger=user.pk)
    
    # testing
    users = User.objects.all()

    context = {"rides_created": rides_created, "rides_registered": rides_registered, "users": users}
    return render(request, "home.html", context)

# Everything to do with recurring rides should be moved to its own app
@login_required
def ride_detail(request, ride_id):
    # Driver and passenger status are fetched in the same query as the ride
    is_passenger = Ride.passenger.through.objects.filter(
        ride=OuterRef("pk"), user=request.user.pk
    )
    ride = get_object_or_404(
        Ride.objects.select_related("driver").annotate(is_passenger=Exists(is_passenger)),
        pk=ride_id,
    )
    is_driver = ride.driver_id == request.user.id

    # leaving_at = f"{l_weekday.title()}, {str(l_hour).zfill(2)}:{str(l_minute).zfill(2)}"
    
    # leaving_at = f"{str(l_hour).zfill(2)}:{str(l_minute).zfill(2)}"
    # arriving_at = f"{str(a_hour).zfill(2)}:{str(a_minute).zfill(2)}"

    context = {
        "ride": ride, 
        "is_driver": is_driver, 
        "is_passenger": ride.is_passenger,
        # "leaving_at": leaving_at,
        # "arriving_at": arriving_at,
        "vias": ride.via_points.all(),
    }
    
    return render(request, "ride_detail.html", context)

# join, leave and delete work on the ride id directly, without loading the ride

@login_required
def join_ride(request):
    ride_id = get_ride_id(request)
    try:
        with transaction.atomic():
            request.user.passenger.add(ride_id)
    except IntegrityError:
        # The ride does not exist
        raise Http404

    return HttpResponseRedirect(f"/app/ride/{ride_id}/")

@login_required
def leave_ride(request):
    ride_id = get_ride_id(request)
    request.user.passenger.remove(ride_id)

    return HttpResponseRedirect(f"/app/ride/{ride_id}/")

@login_required
def delete_ride(request):
    ride_id = get_ride_id(request)
    # Only deletes the ride if the user is its driver
    Ride.objects.filter(pk=ride_id, driver=request.user).delete()

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

    if request.method != "POST":
        context["form"] = SearchForm()
        return render(request, "search.html", context)

    search_form = SearchForm(request.POST)
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

@login_required
def add_ride(request):    

    day_list = [
        (_("Mon"), "monday"),
        (_("Tue"), "tuesday"),
        (_("Wed"), "wednesday"),
        (_("Thu"), "thursday"),
        (_("Fri"), "friday"),
        (_("Sat"), "saturday"),
        (_("Sun"), "sunday")
    ]

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

                ride.one_time = True if request.POST["one_time"] == "oneTime" else False
                ride.one_way = True if request.POST["one_way"] == "oneWay" else False

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
            except Exception as e:
                context = {
                    "ride_form": ride_form,
                    "day_list": day_list,
                    "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"), "campuses": CAMPUSES,
                }
                
                return render(request, "add_ride.html", context)
            return HttpResponseRedirect(f"/app/ride/{ride.id}")
            # return HttpResponseRedirect("/app/home")

        else:
            context = {
                "ride_form": ride_form,
                "day_list": day_list,
                "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"), "campuses": CAMPUSES,
            }

            return render(request, "add_ride.html", context)
    else:
        # from_address_form = AddressForm()
        # to_address_form = AddressForm()
        ride_form = RideForm()

    context = {
        "ride_form": ride_form,
        "day_list": day_list,
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