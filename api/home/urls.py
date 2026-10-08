from django.urls import path, include
from .views import *

urlpatterns = [
    path("", index, name="index"),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("ride/join_ride", join_ride, name="join_ride"),
    path("ride/leave_ride", leave_ride, name="leave_ride"),
    path("ride/delete_ride", delete_ride, name="delete_ride"),
    path("ride/<uuid:ride_id>/", ride_detail, name="ride_detail"), 
    path("home/", home, name="home"),
    path("search/", search, name="search"),
    path("add/", add_ride, name="add"),
    path("digitrans/autocomplete/", digitrans_autocomplete_proxy, name="digitrans_autocomplete_proxy")
]