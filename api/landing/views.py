from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import datetime

@login_required
def landing(request):
    current_year = datetime.now().year
    return render(request, "landing.html", {"current_year": current_year})

@login_required
def how_it_works(request):
    return render(request, "how-it-works.html")

@login_required
def impact(request):
    return render(request, "impact.html")

@login_required
def faq(request):
    return render(request, "faq.html")

@login_required
def contact(request):
    return render(request, "contact.html")
