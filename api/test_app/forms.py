from django import forms
from .models import Address, Ride
from django.forms import modelformset_factory

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

# class AddressCharForm(forms.ModelForm):
#     class Meta:
#         model = AddressChar
#         fields = ("address")

# AddressFormSet = modelformset_factory(
#     AddressChar, fields=("address"),
# )

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
            "one_time",
            "one_way",
            "leaving_at_date_time",
            "returning_at_date_time",
            "monday_check",
            "monday_leaving_at_time",
            "monday_returning_at_time",
            "tuesday_check",
            "tuesday_leaving_at_time",
            "tuesday_returning_at_time",
            "wednesday_check",
            "wednesday_leaving_at_time",
            "wednesday_returning_at_time",
            "thursday_check",
            "thursday_leaving_at_time",
            "thursday_returning_at_time",
            "friday_check",
            "friday_leaving_at_time",
            "friday_returning_at_time",
            "saturday_check",
            "saturday_leaving_at_time",
            "saturday_returning_at_time",
            "sunday_check",
            "sunday_leaving_at_time",
            "sunday_returning_at_time",
            "note",
            # "test",
            # "private",
        )