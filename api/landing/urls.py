from django.urls import path
from .views import *

urlpatterns = [
    path("", landing, name="landing"),
    path("impact", impact, name="impact"),
    path("faq", faq, name="faq"),
    path("safety", safety, name="safety"),
    path("terms-of-use", terms_of_use, name="terms-of-use"),
    path("privacy-policy", privacy_policy, name="privacy-policy"),
    path("how-it-works", how_it_works, name="how-it-works"),
    path("contact", contact, name="contact"),
]