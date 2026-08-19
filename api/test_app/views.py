from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from .models import Ride
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
import traceback

def offline(request):
    return render(request, "offline-new.html")

@login_required
def index(request):
    return HttpResponseRedirect("/app/home/")

@login_required
def old_index(request):
    ride_list = Ride.objects.order_by("-created_at")
    User = get_user_model()
    users = User.objects.all()
    # template = loader.get_template("static/index.html")
    context = {"ride": ride_list, "users": users}

    return render(request, "index.html", context)

@login_required
def my_rides(request):
    user = request.user
    ride_list = user.rides.all()
    context = {"rides": ride_list}

    return render(request, "my_rides.html", context)

# Everything to do with recurring rides should be moved to its own app
@login_required
def ride_detail(request, ride_id):
    ride = get_object_or_404(Ride, pk=ride_id)
    is_driver = True if ride.driver.id == request.user.id else False
    is_passenger = True if request.user in ride.passenger.all() else False

    # leaving_at = f"{l_weekday.title()}, {str(l_hour).zfill(2)}:{str(l_minute).zfill(2)}"
    
    # leaving_at = f"{str(l_hour).zfill(2)}:{str(l_minute).zfill(2)}"
    # arriving_at = f"{str(a_hour).zfill(2)}:{str(a_minute).zfill(2)}"

    context = {
        "ride": ride, 
        "is_driver": is_driver, 
        "is_passenger": is_passenger,
        # "leaving_at": leaving_at,
        # "arriving_at": arriving_at,
        "num_passengers": len(ride.passenger.all()),
        "vias": ", ".join(ride.vias)
    }
    
    return render(request, "ride_detail.html", context)

@login_required
def join_ride(request):
    user, ride, response = ride_helper(request)
    ride.passenger.add(user)
    user.rides.add(ride)

    return response

@login_required
def leave_ride(request):
    user, ride, response = ride_helper(request)
    ride.passenger.remove(user)
    user.rides.remove(ride)

    return response

@login_required
def delete_ride(request):
    user, ride, response = ride_helper(request)

    if ride.driver.id == user.id:
        ride.delete()
        return HttpResponseRedirect("/")
    else:
        return HttpResponseRedirect("/")

def ride_helper(request):
    post_data = request.POST
    rt_id = post_data.get("ride")
    ride = get_object_or_404(Ride, pk=rt_id)
    user = request.user
    response = HttpResponseRedirect(f"/recurring-ride/{rt_id}/")

    return user, ride, response