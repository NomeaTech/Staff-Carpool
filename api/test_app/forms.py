from django import forms
from .models import Address, Recurring_Trip

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = (
            "country",
            "city",
            "postcode",
            "street",
            "number"
        )

class RecurringTripForm(forms.ModelForm):
    class Meta:
        model = Recurring_Trip
        fields = (
            # "start",
            # "destination",
            # "leaving_at",
            # "arriving_at",
            "private",
        )