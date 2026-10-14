from datetime import datetime, time

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import Address, Ride
from django.forms import modelformset_factory

# Dates and times are stored as datetime-local / time input strings
DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M"
TIME_FORMAT = "%H:%M"

WEEKDAYS = [
    ("monday", _("Monday")),
    ("tuesday", _("Tuesday")),
    ("wednesday", _("Wednesday")),
    ("thursday", _("Thursday")),
    ("friday", _("Friday")),
    ("saturday", _("Saturday")),
    ("sunday", _("Sunday")),
]

def parse_date_time(value):
    """A datetime-local value ("2026-10-12T08:30") as a naive datetime, or None."""
    try:
        parsed = datetime.fromisoformat(value or "")
    except ValueError:
        return None
    return None if parsed.tzinfo else parsed.replace(second=0, microsecond=0)

def parse_time(value):
    """A time input value ("08:30") as a time, or None."""
    try:
        parsed = time.fromisoformat(value or "")
    except ValueError:
        return None
    return None if parsed.tzinfo else parsed.replace(second=0, microsecond=0)

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
    """
    The add ride form. Its schedule depends on two choices:
    - one-time rides need a departure date and time, recurring rides at
      least one day with a departure time on each chosen day
    - return rides also need a return date and time (one-time rides) or a
      return time on each chosen day (recurring rides), after the departure
    Values that do not apply to the chosen kind of ride are cleared.
    add_ride.html marks the inputs that are needed as required, so that the
    browser asks for them before posting.
    """
    one_time = forms.TypedChoiceField(
        choices=[("oneTime", _("One-time")), ("recurring", _("Recurring"))],
        coerce=lambda value: value == "oneTime",
        error_messages={"required": _("Choose whether the ride is one-time or recurring.")},
    )
    one_way = forms.TypedChoiceField(
        choices=[("oneWay", _("One-way")), ("twoWay", _("Return"))],
        coerce=lambda value: value == "oneWay",
        error_messages={"required": _("Choose whether the ride is one-way or has a return journey.")},
    )

    def clean(self):
        data = super().clean()
        one_time, one_way = data.get("one_time"), data.get("one_way")
        if one_time is None or one_way is None:
            return data

        if one_time:
            self.clean_one_time_schedule(data, one_way)
            for day, _name in WEEKDAYS:
                data[f"{day}_check"] = False
                data[f"{day}_leaving_at_time"] = data[f"{day}_returning_at_time"] = ""
        else:
            self.clean_recurring_schedule(data, one_way)
            data["leaving_at_date_time"] = data["returning_at_date_time"] = ""
        return data

    def clean_one_time_schedule(self, data, one_way):
        leaving = parse_date_time(data.get("leaving_at_date_time"))
        now = timezone.localtime().replace(tzinfo=None, second=0, microsecond=0)
        if leaving is None:
            self.add_error("leaving_at_date_time", _("Enter the date and time the ride leaves."))
        elif leaving < now:
            self.add_error("leaving_at_date_time", _("The ride cannot leave in the past."))
        else:
            data["leaving_at_date_time"] = leaving.strftime(DATE_TIME_FORMAT)

        if one_way:
            data["returning_at_date_time"] = ""
            return
        returning = parse_date_time(data.get("returning_at_date_time"))
        if returning is None:
            self.add_error("returning_at_date_time", _("Enter the date and time of the return journey."))
        elif leaving is not None and returning <= leaving:
            self.add_error("returning_at_date_time", _("The return journey must be after the departure."))
        else:
            data["returning_at_date_time"] = returning.strftime(DATE_TIME_FORMAT)

    def clean_recurring_schedule(self, data, one_way):
        if not any(data.get(f"{day}_check") for day, _name in WEEKDAYS):
            self.add_error(None, _("Choose at least one day for a recurring ride."))

        for day, name in WEEKDAYS:
            leaving_field, returning_field = f"{day}_leaving_at_time", f"{day}_returning_at_time"
            if not data.get(f"{day}_check"):
                data[leaving_field] = data[returning_field] = ""
                continue

            leaving = parse_time(data.get(leaving_field))
            if leaving is None:
                self.add_error(leaving_field, _("Enter the time the ride leaves on %(day)s.") % {"day": name})
            else:
                data[leaving_field] = leaving.strftime(TIME_FORMAT)

            if one_way:
                data[returning_field] = ""
                continue
            returning = parse_time(data.get(returning_field))
            if returning is None:
                self.add_error(returning_field, _("Enter the time of the return journey on %(day)s.") % {"day": name})
            elif leaving is not None and returning <= leaving:
                self.add_error(returning_field, _("The return journey on %(day)s must be after the departure.") % {"day": name})
            else:
                data[returning_field] = returning.strftime(TIME_FORMAT)

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
            "start_json",
            "destination_json",
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
        error_messages = {
            "start_json": {"required": _("Choose a start location from the list.")},
            "destination_json": {"required": _("Choose a destination from the list.")},
        }