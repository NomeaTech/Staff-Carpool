from django.urls import path
from .views import my_trips, index, recurring_trip_detail, join_trip, delete_trip, leave_trip

urlpatterns = [
    path("", index, name="index"),
    path("my-trips/", my_trips, name="my_trips"),
    path("recurring-trip/join_trip", join_trip, name="join_trip"),
    path("recurring-trip/leave_trip", leave_trip, name="leave_trip"),
    path("recurring-trip/delete_trip", delete_trip, name="delete_trip"),
    path("recurring-trip/<int:recurring_trip_id>/", recurring_trip_detail, name="recurring_trip_detail")
]