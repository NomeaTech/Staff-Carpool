from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from test_app.models import Ride
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from test_app.models import Ride
from .forms import SearchForm
from accounts.models import User
from test_app.forms import AddressForm, RideForm
import traceback
import logging
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

@login_required
def app_index(request):
    return HttpResponseRedirect("/apps/home/")

@login_required
def home(request):
    user = request.user

    rides_created = Ride.objects.filter(driver=user.pk)
    rides_registered = Ride.objects.filter(passenger=user.pk)
    
    # testing
    users = User.objects.all()

    # for ride in ride_list:
    #     l_weekday = ride.leaving_at_weekday
    #     l_hour = ride.leaving_at_hour
    #     l_minute = ride.leaving_at_minute

    #     a_weekday = ride.arriving_at_weekday
    #     a_hour = ride.arriving_at_hour
    #     a_minute = ride.arriving_at_minute

    context = {"rides_created": rides_created, "rides_registered": rides_registered, "users": users}
    return render(request, "home.html", context)

@login_required
def search(request):
    search_form = SearchForm

    if request.method == "POST":
        search_form = SearchForm(request.POST)
        
        if search_form.is_valid():
            form_clean = search_form.cleaned_data
            start = form_clean["start"]
            destination = form_clean["destination"]
            offer_ride = form_clean["offer"]
            request_ride = form_clean["request"]
            other_ride = form_clean["other"]
            
            # Simple search implementation for now. 
            # Will expand later to make search less tedious
            
            found = True

            # Switch to trigram_similar at some point
            if start or destination or offer_ride or request_ride or other_ride:
                rides = Ride.objects.filter(dest_name__icontains=destination)
            else:
                rides = Ride.objects.all()

            if not rides:
                found = False
            
            context = {"form": search_form, "rides": rides, "start": start, "searched": True, "found": found}
        else:
            context = {"form": search_form}
    else:
        context = {"form": search_form}

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
        logger.debug("add_ride post triggered 1234")
        # from_address_form = AddressForm(request.POST)
        # to_address_form = AddressForm(request.POST)
        logger.debug(request.POST)

        ride_form = RideForm(request.POST)
        if ride_form.is_valid():
            try:
                ride = ride_form.save(commit=False)
                # from_address = from_address_form.save()
                # to_address = to_address_form.save()
                
                # ride.start = from_address
                # ride.destination = to_address

                # collect vias

                for key, value in request.POST.items():
                    if key.startswith("via_input_"):
                        ride.vias.append(value)

                ride.one_time = True if request.POST["one_time"] == "oneTime" else False
                ride.one_way = True if request.POST["one_way"] == "oneWay" else False

                ride.driver = request.user
                ride.save()
            except Exception as e:
                traceback.print_exc()
            # return HttpResponseRedirect(f"/ride/{ride.id}")
            return HttpResponseRedirect("/app/home")

        else:
            context = {
                "ride_form": ride_form,
                "day_list": day_list,
            }

            return render(request, "add_ride.html", context)
    else:
        # from_address_form = AddressForm()
        # to_address_form = AddressForm()
        ride_form = RideForm()

    context = {
        "ride_form": ride_form,
        "day_list": day_list,
    }

    return render(request, "add_ride.html", context)