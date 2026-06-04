from django.urls import path
from .views import my_trips, index

urlpatterns = [
    path("", index, name="index"),
    path("my-trips/", my_trips, name="my_trips"),
]