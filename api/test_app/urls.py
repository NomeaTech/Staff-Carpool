from django.urls import path
from .views import *
from landing.views import landing

urlpatterns = [
    path("", landing, name="landing"),
    path("offline/", offline, name="offline"),
]