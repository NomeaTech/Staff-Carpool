from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from test_app.models import Recurring_Trip
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from test_app.models import Recurring_Trip
from .forms import SearchForm
from accounts.models import User
import traceback

@login_required
def app_index(request):
    return HttpResponseRedirect("/apps/home/")

@login_required
def home(request):
    user = request.user
    trip_list = user.recurring_trips.all()
    
    # testing
    users = User.objects.all()

    # for recurring_trip in trip_list:
    #     l_weekday = recurring_trip.leaving_at_weekday
    #     l_hour = recurring_trip.leaving_at_hour
    #     l_minute = recurring_trip.leaving_at_minute

    #     a_weekday = recurring_trip.arriving_at_weekday
    #     a_hour = recurring_trip.arriving_at_hour
    #     a_minute = recurring_trip.arriving_at_minute

    context = {"recurring_trips": trip_list, "users": users}
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
            
            trips = Recurring_Trip.objects.filter(destName__contains=query)
            context = {"form": search_form, "recurring_trips": trips, "search_query": query, "searched": True}
    else:
        context = {"form": search_form}

    return render(request, "search.html", context)