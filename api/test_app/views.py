from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, Http404
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from .models import Ride
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required

def offline(request):
    return render(request, "offline-new.html")

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
    ride_list = user.passenger.all()
    context = {"rides": ride_list}

    return render(request, "my_rides.html", context)

# Everything to do with recurring rides should be moved to its own app
@login_required
def ride_detail(request, ride_id):
    # Driver and passenger status are fetched in the same query as the ride
    is_passenger = Ride.passenger.through.objects.filter(
        ride=OuterRef("pk"), user=request.user.pk
    )
    ride = get_object_or_404(
        Ride.objects.select_related("driver").annotate(is_passenger=Exists(is_passenger)),
        pk=ride_id,
    )
    is_driver = ride.driver_id == request.user.id

    # leaving_at = f"{l_weekday.title()}, {str(l_hour).zfill(2)}:{str(l_minute).zfill(2)}"
    
    # leaving_at = f"{str(l_hour).zfill(2)}:{str(l_minute).zfill(2)}"
    # arriving_at = f"{str(a_hour).zfill(2)}:{str(a_minute).zfill(2)}"

    context = {
        "ride": ride, 
        "is_driver": is_driver, 
        "is_passenger": ride.is_passenger,
        # "leaving_at": leaving_at,
        # "arriving_at": arriving_at,
        "vias": ride.via_points.all(),
    }
    
    return render(request, "ride_detail.html", context)

# join, leave and delete work on the ride id directly, without loading the ride

@login_required
def join_ride(request):
    ride_id = get_ride_id(request)
    try:
        with transaction.atomic():
            request.user.passenger.add(ride_id)
    except IntegrityError:
        # The ride does not exist
        raise Http404

    return HttpResponseRedirect(f"/ride/{ride_id}/")

@login_required
def leave_ride(request):
    ride_id = get_ride_id(request)
    request.user.passenger.remove(ride_id)

    return HttpResponseRedirect(f"/ride/{ride_id}/")

@login_required
def delete_ride(request):
    ride_id = get_ride_id(request)
    # Only deletes the ride if the user is its driver
    Ride.objects.filter(pk=ride_id, driver=request.user).delete()

    return HttpResponseRedirect("/")

def get_ride_id(request):
    try:
        return int(request.POST.get("ride"))
    except (TypeError, ValueError):
        raise Http404
