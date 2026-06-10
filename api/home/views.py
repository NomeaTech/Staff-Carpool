from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from test_app.models import Recurring_Trip
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
import traceback

@login_required
def home(request):
    user = request.user
    trip_list = user.recurring_trips.all()
    context = {"recurring_trips": trip_list}

    return render(request, "home.html", context)

@login_required
def app_index(request):
    return HttpResponseRedirect("/apps/home/")