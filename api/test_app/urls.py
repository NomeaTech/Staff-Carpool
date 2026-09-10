from django.urls import path
from .views import *
from landing.views import landing

urlpatterns = [
    path("", landing, name="landing"),
    path("offline/", offline, name="offline"),
    path("ride/join_ride", join_ride, name="join_ride"),
    path("ride/leave_ride", leave_ride, name="leave_ride"),
    path("ride/delete_ride", delete_ride, name="delete_ride"),
    path("ride/<int:ride_id>/", ride_detail, name="ride_detail"),
]