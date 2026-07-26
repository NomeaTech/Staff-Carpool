from django.urls import path
from .views import *

urlpatterns = [
    path("home/", home, name="home"),
    # path("", app_index, name="app_index"),
    path("search/", search, name="search"),
    path("add/", add_ride, name="add")
]