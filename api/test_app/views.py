from django.shortcuts import render
from .models import Ride
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required

def offline(request):
    return render(request, "offline-new.html")