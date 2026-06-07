from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
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

# Everything to do with recurring trips should be moved to its own app
@login_required
def recurring_trip_detail(request, recurring_trip_id):
    recurring_trip = get_object_or_404(Recurring_Trip, pk=recurring_trip_id)
    is_driver = True if recurring_trip.driver.id == request.user.id else False
    is_passenger = True if request.user in recurring_trip.passenger.all() else False

    context = {
        "recurring_trip": recurring_trip, 
        "is_driver": is_driver, 
        "is_passenger": is_passenger,
    }
    
    return render(request, "recurring_trip_detail.html", context)

@login_required
def join_trip(request):
    user, trip, response = trip_helper(request)
    trip.passenger.add(user)

    return response

@login_required
def leave_trip(request):
    user, trip, response = trip_helper(request)
    trip.passenger.remove(user)

    return response

@login_required
def delete_trip(request):
    user, trip, response = trip_helper(request)

    if trip.driver.id == user.id:
        trip.delete()
        return HttpResponseRedirect("/")
    else:
        return HttpResponseRedirect("/")

def trip_helper(request):
    post_data = request.POST
    rt_id = post_data.get("recurring_trip")
    trip = get_object_or_404(Recurring_Trip, pk=rt_id)
    user = request.user
    response = HttpResponseRedirect(f"/recurring-trip/{rt_id}/")

    return user, trip, response

@login_required
def create_recurring_trip(request):    
    return render(request, "create_recurring_trip.html")
