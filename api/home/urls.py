from django.urls import path, include
from .views import *

urlpatterns = [
    path("", index, name="index"),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),    
    path("home/", home, name="home"),
    path("search/", search, name="search"),
    path("add/", add_ride, name="add")
]