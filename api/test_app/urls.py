from django.urls import path
from .views import my_trips, index, recurring_trip_detail

urlpatterns = [
    path("", index, name="index"),
    path("my-trips/", my_trips, name="my_trips"),
    path("recurring-trip/<int:recurring_trip_id>/", recurring_trip_detail, name="recurring_trip_detail")
]