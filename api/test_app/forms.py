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
            "offer",
            "request",
            "train",
            "bus",
            "taxi",
            "other",
            "other_field",
            "max_passengers",
            "start",
            "vias",
            "destination",
            "dest_name",
            "leaving_at_date",
            "leaving_at_time",
            "arriving_at_date",
            "arriving_at_time",
            "mo_leaving_at_time",
            "mo_arriving_at_time",
            "tu_leaving_at_time",
            "tu_arriving_at_time",
            "we_leaving_at_time",
            "we_arriving_at_time",
            "th_leaving_at_time",
            "th_arriving_at_time",
            "fr_leaving_at_time",
            "fr_arriving_at_time",
            "sa_leaving_at_time",
            "sa_arriving_at_time",
            "su_leaving_at_time",
            "su_arriving_at_time",
            "note",
            # "test",
            # "private",
        )