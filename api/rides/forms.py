from datetime import datetime, time
import json

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import Ride

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

# A ride can have at most this many stops on the way
MAX_VIAS = 8
# Most passengers a ride offer can take (as on the add ride page)
MAX_SEATS = 100
TRANSPORT_FIELDS = ("offer", "request", "train", "bus", "taxi", "other")

def clean_place(value):
    """
    A place from the location pickers (place.toJSON() of Google Places, or a
    campus from home/campuses.py), or None if it is not one.
    """
    if not isinstance(value, dict) or not isinstance(value.get("displayName"), str) or not value["displayName"].strip():
        return None
    location = value.get("location")
    if not isinstance(location, dict):
        return None
    lat, lng = location.get("lat"), location.get("lng")
    if not all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in (lat, lng)):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return value

def parse_time(value):
    """A time input value ("08:30") as a time, or None."""
    try:
        parsed = time.fromisoformat(value or "")
    except ValueError:
        return None
    return None if parsed.tzinfo else parsed.replace(second=0, microsecond=0)

class RideForm(forms.ModelForm):
    """
    The add and edit ride form (the same checks for both). A ride needs a
    start and destination chosen from the location pickers (stops on the way
    are optional), and at least one way of travelling.

    Its schedule depends on two choices:
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # An existing ride's choices, as the radio buttons' values (a new ride
        # already has its UUID, so instance.pk does not tell them apart)
        if not self.instance._state.adding:
            self.initial["one_time"] = "oneTime" if self.instance.one_time else "recurring"
            self.initial["one_way"] = "oneWay" if self.instance.one_way else "twoWay"

    def clean_start_json(self):
        place = clean_place(self.cleaned_data.get("start_json"))
        if place is None:
            raise forms.ValidationError(self.fields["start_json"].error_messages["required"], code="invalid")
        return place

    def clean_destination_json(self):
        place = clean_place(self.cleaned_data.get("destination_json"))
        if place is None:
            raise forms.ValidationError(self.fields["destination_json"].error_messages["required"], code="invalid")
        return place

    def clean_vias(self):
        """
        Stops on the way, posted as via_<id>_json in the order they are on
        the page. Empty ones (a stop added but not chosen) are left out.
        """
        vias = []
        for key, value in self.data.items():
            if not (key.startswith("via_") and key.endswith("_json")) or not value:
                continue
            try:
                place = clean_place(json.loads(value))
            except ValueError:
                place = None
            if place is None:
                self.add_error(None, _("Choose each stop on the way from the list of suggestions."))
                return []
            vias.append(place)
        if len(vias) > MAX_VIAS:
            self.add_error(None, _("A ride can have at most %(count)s stops on the way.") % {"count": MAX_VIAS})
        return vias[:MAX_VIAS]

    def clean_transport(self, data):
        if not any(data.get(field) for field in TRANSPORT_FIELDS):
            self.add_error(None, _("Choose at least one way of travelling."))
        if data.get("other"):
            data["other_field"] = (data.get("other_field") or "").strip()
            if not data["other_field"]:
                self.add_error("other_field", _("Describe the other way of travelling."))
        else:
            data["other_field"] = None
        # Only ride offers have seats
        if not data.get("offer"):
            data["max_passengers"] = None
        elif "max_passengers" in self.errors:
            pass
        elif data.get("max_passengers") is None:
            self.add_error("max_passengers", _("Enter how many passengers you can take."))
        else:
            if not 1 <= data["max_passengers"] <= MAX_SEATS:
                self.add_error("max_passengers", _("Enter a number of passengers from 1 to %(max)s.") % {"max": MAX_SEATS})
            elif not self.instance._state.adding:
                taken = self.instance.requests.filter(status="accepted").count()
                if data["max_passengers"] < taken:
                    self.add_error("max_passengers", _(
                        "%(count)s passengers have already joined. Remove passengers before lowering the seats below that."
                    ) % {"count": taken})

    def clean(self):
        data = super().clean()
        data["vias"] = self.clean_vias()
        self.clean_transport(data)
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
            "price",
            # "test",
            # "private",
        )
        error_messages = {
            "start_json": {"required": _("Choose a start location from the list."), "invalid": _("Choose a start location from the list.")},
            "destination_json": {"required": _("Choose a destination from the list."), "invalid": _("Choose a destination from the list.")},
        }