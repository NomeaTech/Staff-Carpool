from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import datetime

def landing(request):
    current_year = datetime.now().year
    return render(request, "index.html", {"current_year": current_year})

def contact(request):
    return render(request, "contact.html")

def faq(request):
    return render(request, "faq.html")

def impact(request):
    return render(request, "impact.html")

def safety(request):
    return render(request, "safety.html")

def terms_of_use(request):
    return render(request, "terms-of-use.html")

def privacy_policy(request):
    return render(request, "privacy-policy.html")

def how_it_works(request):
    return render(request, "how-it-works.html")