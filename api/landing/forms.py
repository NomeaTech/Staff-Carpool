from urllib.error import URLError

from django import forms
from django.utils.translation import gettext_lazy as _
from turnstile.fields import TurnstileField

class ContactTurnstileField(TurnstileField):
    """A TurnstileField that shows an error instead of crashing when
    Cloudflare cannot be reached (it only handles HTTP errors itself)."""
    default_error_messages = {
        "error_turnstile": _("Human verification could not be completed. Please try again."),
        "invalid_turnstile": _("Human verification failed. Please try again."),
        "required": _("Please complete the human verification."),
    }

    def validate(self, value):
        try:
            super().validate(value)
        except (URLError, TimeoutError, ValueError):
            raise forms.ValidationError(self.error_messages["error_turnstile"], code="error_turnstile")

class ContactForm(forms.Form):
    name = forms.CharField(required=True, max_length=100)
    email = forms.EmailField(required=True)
    message = forms.CharField(required=True, max_length=5000)
    turnstile = ContactTurnstileField()
