from django import forms
from .models import Address

class AddressForm(forms.ModelForm):
    model = Address
    fields = (
        
    )