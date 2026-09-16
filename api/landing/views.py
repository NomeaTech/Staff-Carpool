from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import datetime
from .forms import ContactForm

@login_required
def landing(request):
    current_year = datetime.now().year
    return render(request, "index.html", {"current_year": current_year})

@login_required
def contact(request):
    if request.method == "POST":
        contact_form = ContactForm(request.POST)
        if contact_form.is_valid():
            try:
                pass
            except:
                pass
        else:
            context = {"form": contact_form}
            return render(request, "contact.html", context)
    else:
        contact_form = ContactForm()
        context = {"form": contact_form}
        return render(request, "contact.html", context)

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

@login_required
def how_it_works(request):
    return render(request, "how-it-works.html")