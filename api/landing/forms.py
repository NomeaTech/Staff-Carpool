from django import forms
from turnstile.fields import TurnstileField

class ContactForm(forms.Form):
    name = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    message = forms.CharField(required=True)
    turnstile = TurnstileField()