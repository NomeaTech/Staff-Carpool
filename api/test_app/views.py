from django.shortcuts import render, get_object_or_404
from .models import Recurring_Trip
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    trip_list = Recurring_Trip.objects.order_by("-created_at")
    User = get_user_model()
    users = User.objects.all()
    # template = loader.get_template("static/index.html")
    context = {"recurring_trip": trip_list, "users": users}

    return render(request, "index.html", context)

@login_required
def my_trips(request):
    user = request.user
    trip_list = user.recurring_trips.all()
    context = {"recurring_trips": trip_list}

    return render(request, "my_trips.html", context)

@login_required
def recurring_trip_detail(request, recurring_trip_id):
    recurring_trip = get_object_or_404(Recurring_Trip, pk=recurring_trip_id)
    is_driver = True if recurring_trip.driver.id == request.user.id else False
    is_passenger = True if request.user in recurring_trip.passenger.all() else False

    context = {
        "recurring_trip": recurring_trip, 
        "is_driver": is_driver, 
        "is_passenger": is_passenger
    }
    
    return render(request, "recurring_trip_detail.html", context)
 