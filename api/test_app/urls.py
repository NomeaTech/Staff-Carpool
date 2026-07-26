from django.urls import path
from .views import *

urlpatterns = [
    path("", index, name="index"),
    path("offline/", offline, name="offline"),
    path("my-rides/", my_rides, name="my_rides"),
    path("ride/join_ride", join_ride, name="join_ride"),
    path("ride/leave_ride", leave_ride, name="leave_ride"),
    path("ride/delete_ride", delete_ride, name="delete_ride"),
    path("ride/<int:ride_id>/", ride_detail, name="ride_detail"),
]