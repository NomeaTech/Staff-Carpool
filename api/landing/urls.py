from django.urls import path
from .views import *

urlpatterns = [
    path("", landing, name="landing"),
    path("how-it-works", how_it_works, name="how-it-works"),
    path("impact", impact, name="impact"),
    path("faq", faq, name="faq"),
    path("contact", contact, name="contact")
]