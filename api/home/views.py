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

@login_required
def app_index(request):
    return HttpResponseRedirect("/apps/home/")

@login_required
def home(request):
    user = request.user
    ride_list = user.rides.all()
    
    # testing
    users = User.objects.all()

    # for ride in ride_list:
    #     l_weekday = ride.leaving_at_weekday
    #     l_hour = ride.leaving_at_hour
    #     l_minute = ride.leaving_at_minute

    #     a_weekday = ride.arriving_at_weekday
    #     a_hour = ride.arriving_at_hour
    #     a_minute = ride.arriving_at_minute

    context = {"rides": ride_list, "users": users}
    return render(request, "home.html", context)

@login_required
def search(request):
    search_form = SearchForm

    if request.method == "POST":
        search_form = SearchForm(request.POST)
        
        if search_form.is_valid():
            form_clean = search_form.cleaned_data
            query = form_clean["search_query"]
            
            # Simple search implementation for now. 
            # Will expand later to make search less tedious
            
            rides = Ride.objects.filter(destName__contains=query)
            context = {"form": search_form, "rides": rides, "search_query": query, "searched": True}
    else:
        context = {"form": search_form}

    return render(request, "search.html", context)

@login_required
def add_ride(request):    
    if request.method == "POST":
        from_address_form = AddressForm(request.POST)
        to_address_form = AddressForm(request.POST)
        ride_form = RideForm(request.POST)
        if ride_form.is_valid() and to_address_form.is_valid() and from_address_form.is_valid():
            
            success = True

            try:            
                ride = ride_form.save(commit=False)
                from_address = from_address_form.save()
                to_address = to_address_form.save()
                
                ride.start = from_address
                ride.destination = to_address

                ride.driver = request.user

                ride.save()
            except Exception as e:
                traceback.print_exc()
                
            return HttpResponseRedirect(f"/ride/{ride.id}")
            # return render(request, "ride_created.html", context)
    else:
        from_address_form = AddressForm()
        to_address_form = AddressForm()
        ride_form = RideForm()

    context = {
        "from_address_form": from_address_form,
        "to_address_form": to_address_form,
        "Ride_form": ride_form
    }

    return render(request, "add_ride.html", context)