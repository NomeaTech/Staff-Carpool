import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from datetime import datetime
from .forms import ContactForm

logger = logging.getLogger(__name__)

@login_required
def landing(request):
    current_year = datetime.now().year
    return render(request, "index.html", {"current_year": current_year})

@login_required
def contact(request):
    if request.method != "POST":
        return render(request, "contact.html", {"form": ContactForm()})

    contact_form = ContactForm(request.POST)
    if not contact_form.is_valid():
        # Includes a failed Turnstile check
        return render(request, "contact.html", {"form": contact_form})

    data = contact_form.cleaned_data
    # Newlines are not allowed in an email header
    name = " ".join(data["name"].split())
    email = EmailMessage(
        subject=f"LUT Kyyti contact form: {name}",
        body=(
            f"Name: {name}\n"
            f"Email: {data['email']}\n"
            f"Account: {request.user.email}\n"
            f"\n{data['message']}\n"
        ),
        to=[settings.CONTACT_EMAIL],
        # Replying answers the person who sent the message
        reply_to=[data["email"]],
    )
    try:
        email.send()
    except Exception:
        logger.exception("Could not send a contact form message")
        contact_form.add_error(None, _("Your message could not be sent. Please try again later."))
        return render(request, "contact.html", {"form": contact_form})

    # Redirect, so that reloading the page does not send the message again
    messages.success(request, _("Thank you! Your message has been sent."))
    return redirect("contact")

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