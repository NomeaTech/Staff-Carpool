from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import datetime

@login_required
def landing(request):
    current_year = datetime.now().year
    return render(request, "index.html", {"current_year": current_year})

@login_required
def contact(request):
    return render(request, "contact.html")

@login_required
def faq(request):
    return render(request, "faq.html")

@login_required
def impact(request):
    return render(request, "impact.html")

@login_required
def safety(request):
    return render(request, "safety.html")

@login_required
def terms_of_use(request):
    return render(request, "terms-of-use.html")

@login_required
def privacy_policy(request):
    return render(request, "privacy-policy.html")