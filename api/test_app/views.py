from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from .models import Recurring_Trip
import os.path

def index(request):
    trip_list = Recurring_Trip.objects.order_by("-created_at")
    # template = loader.get_template("static/index.html")
    context = {"recurring_trip": trip_list}

    return render(request, "index.html", context)