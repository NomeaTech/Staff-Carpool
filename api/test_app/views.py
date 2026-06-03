from django.shortcuts import render
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