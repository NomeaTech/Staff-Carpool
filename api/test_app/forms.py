from django import forms
from .models import Address, Ride

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

class RideForm(forms.ModelForm):
    class Meta:
        model = Ride
        fields = (
            # "start",
            # "destination",
            "test",
            "private",
            "max_passengers",
            "leaving_at_weekday",
            "leaving_at_hour",
            "leaving_at_minute",
            "arriving_at_weekday",
            "arriving_at_hour",
            "arriving_at_minute",
            "destName",
            "note",
        )