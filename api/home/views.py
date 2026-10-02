from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from test_app.models import Ride, Via
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from test_app.models import Ride
from .forms import SearchForm
from accounts.models import User
from test_app.forms import AddressForm, RideForm
import traceback
import logging
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse, HttpResponseBadRequest
from django.db.models import Q, Exists, OuterRef, Subquery
from django.db.models.functions import Least
from django.db import transaction
import os
import requests
from django.views.decorators.cache import never_cache, cache_control
import json
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance

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

@login_required
@never_cache
def search(request):
    search_form = SearchForm

    if request.method == "POST":
        search_form = SearchForm(request.POST)
        
        if search_form.is_valid():
            form_clean = search_form.cleaned_data
            start_json = form_clean["start_json"]
            destination_json = form_clean["destination_json"]
            offer_ride = form_clean["offer"]
            request_ride = form_clean["request"]
            other_ride = form_clean["other"]
            
            # Simple search implementation for now. 
            # Will expand later to make search less tedious
            
            found = True

            rides = Ride.objects.all()

            
            

            if start_json:
                sl = start_json["location"]
                start_location = Point(sl["lng"], sl["lat"], srid=4326)

                rides = rides.filter(start_location__distance_lte=(start_location, D(km=30))).annotate(dist=Distance("start_location", start_location)).order_by("dist")
            if destination_json:
                dl = destination_json["location"]
                destination_location = Point(dl["lng"], dl["lat"], srid=4326)
                
                # Match rides that end near the destination or pass by it on a via
                vias_near = Via.objects.filter(
                    ride=OuterRef("pk"),
                    location__distance_lte=(destination_location, D(km=30)),
                )
                closest_via = Via.objects.filter(
                    ride=OuterRef("pk")
                ).annotate(
                    d=Distance("location", destination_location)
                ).order_by("d").values("d")[:1]

                rides = rides.filter(
                    Q(destination_location__distance_lte=(destination_location, D(km=30))) |
                    Exists(vias_near)
                ).annotate(
                    dist=Least(
                        Distance("destination_location", destination_location),
                        Subquery(closest_via),
                    )
                ).order_by("dist")
            if offer_ride:
                rides = rides.filter(offer=offer_ride)
            if request_ride:
                rides = rides.filter(request=request_ride)
            if other_ride:
                rides = rides.filter(
                    Q(other=True) | 
                    Q(train=True) | 
                    Q(bus=True) | 
                    Q(taxi=True)
                )
                # rides = rides.filter(other=other_ride)

            if not rides:
                found = False
            
            context = {"form": search_form, "rides": rides, "searched": True, "found": found, "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"),}
        else:
            context = {"form": search_form, "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"),}
    else:
        context = {"form": search_form, "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"),}

    return render(request, "search.html", context)

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
                    for order, via_json in enumerate(vias_json[:8]):
                        vl = via_json["location"]
                        Via.objects.create(
                            ride=ride,
                            order=order,
                            via_json=via_json,
                            location=Point(vl["lng"], vl["lat"], srid=4326),
                        )
            except Exception as e:
                context = {
                    "ride_form": ride_form,
                    "day_list": day_list,
                    "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"),
                }
                
                return render(request, "add_ride.html", context)
            return HttpResponseRedirect(f"/ride/{ride.id}")
            # return HttpResponseRedirect("/app/home")

        else:
            context = {
                "ride_form": ride_form,
                "day_list": day_list,
                "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"),
            }

            return render(request, "add_ride.html", context)
    else:
        # from_address_form = AddressForm()
        # to_address_form = AddressForm()
        ride_form = RideForm()

    context = {
        "ride_form": ride_form,
        "day_list": day_list,
        "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"),
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