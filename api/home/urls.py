from django.urls import path, include
from .views import *

urlpatterns = [
    path("", index, name="index"),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("ride/delete_ride", delete_ride, name="delete_ride"),
    path("ride/<uuid:ride_id>/", ride_detail, name="ride_detail"),
    path("ride/<uuid:ride_id>/edit/", edit_ride, name="edit_ride"),
    path("ride/<uuid:ride_id>/request/", request_ride, name="request_ride"),
    path("ride/<uuid:ride_id>/withdraw/", withdraw_request, name="withdraw_request"),
    path("ride/<uuid:ride_id>/report/", report_member, name="report_member"),
    path("ratings/", ratings_page, name="ratings"),
    path("requests/<uuid:request_id>/answer/", answer_request, name="answer_request"),
    path("home/", home, name="home"),
    path("home/welcomed/", welcomed, name="welcomed"),
    path("rides/", my_rides, name="my_rides"),
    path("more/", more, name="more"),
    path("support/report/", report_bug, name="report_bug"),
    path("notifications/", include("notifications.urls")),
    path("groups/", include("groups.urls")),
    path("search/", search, name="search"),
    path("add/", add_ride, name="add"),
    path("digitrans/autocomplete/", digitrans_autocomplete_proxy, name="digitrans_autocomplete_proxy")
]