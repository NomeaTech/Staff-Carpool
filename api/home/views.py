from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from test_app.models import Recurring_Trip
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
import traceback

@login_required
def app_index(request):
    return HttpResponseRedirect("/apps/home/")

@login_required
def home(request):
    user = request.user
    trip_list = user.recurring_trips.all()

    for recurring_trip in trip_list:
        l_weekday = recurring_trip.leaving_at_weekday
        l_hour = recurring_trip.leaving_at_hour
        l_minute = recurring_trip.leaving_at_minute

        a_weekday = recurring_trip.arriving_at_weekday
        a_hour = recurring_trip.arriving_at_hour
        a_minute = recurring_trip.arriving_at_minute

    context = {"recurring_trips": trip_list}
    return render(request, "home.html", context)