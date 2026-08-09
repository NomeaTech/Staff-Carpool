from django.db import models

from django_geoaddress.fields import GeoaddressField
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.utils.translation import gettext as _
from itertools import compress
from dateutil import parser
from dateutil.parser import ParserError
from datetime import datetime


class Address(models.Model):
    country = models.CharField(max_length=200)
    city = models.CharField(max_length=200)
    postcode = models.CharField(max_length=200)
    street = models.CharField(max_length=200)
    number = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.country}, {self.city}, {self.postcode}, {self.street} {self.number}"

# class AddressChar(models.Model):
    # address = models.CharField(max_length=100)

class Ride(models.Model):
    # test = GeoaddressField()

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="driver"
    )

    passenger = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name="passenger",
        blank=True,
        null=True
    )
    
    # Car Ride
    offer = models.BooleanField(default=False)
    request = models.BooleanField(default=False)

    # Other Transport
    train = models.BooleanField(default=False)
    bus = models.BooleanField(default=False)
    taxi = models.BooleanField(default=False)
    other = models.BooleanField(default=False)
    
    other_field = models.CharField(blank=True, null=True)
    max_passengers = models.IntegerField()

    # Address
    start = models.CharField()
    vias = ArrayField(
        models.CharField(blank=True),
        blank=True,
        null=True,
    )
    destination = models.CharField()
    dest_name = models.CharField(help_text="Destination name")

    # Schedule

    one_time = models.BooleanField(default=True)
    one_way = models.BooleanField(default=True)

    leaving_at_date_time = models.CharField(blank=True)
    # leaving_at_hour = models.IntegerField(blank=True)
    # leaving_at_minute = models.IntegerField(blank=True)

    returning_at_date_time = models.CharField(blank=True)
    # arriving_at_hour = models.IntegerField(blank=True)
    # arriving_at_minute = models.IntegerField(blank=True)

    # Recurring days

    monday_check = models.BooleanField(default=False)
    monday_leaving_at_time = models.CharField(blank=True)
    monday_returning_at_time = models.CharField(blank=True)

    tuesday_check = models.BooleanField(default=False)
    tuesday_leaving_at_time = models.CharField(blank=True)
    tuesday_returning_at_time = models.CharField(blank=True)

    wednesday_check = models.BooleanField(default=False)
    wednesday_leaving_at_time = models.CharField(blank=True)
    wednesday_returning_at_time = models.CharField(blank=True)

    thursday_check = models.BooleanField(default=False)
    thursday_leaving_at_time = models.CharField(blank=True)
    thursday_returning_at_time = models.CharField(blank=True)

    friday_check = models.BooleanField(default=False)
    friday_leaving_at_time = models.CharField(blank=True)
    friday_returning_at_time = models.CharField(blank=True)

    saturday_check = models.BooleanField(default=False)
    saturday_leaving_at_time = models.CharField(blank=True)
    saturday_returning_at_time = models.CharField(blank=True)

    sunday_check = models.BooleanField(default=False)
    sunday_leaving_at_time = models.CharField(blank=True)
    sunday_returning_at_time = models.CharField(blank=True)

    note = models.TextField(blank=True, default="", help_text="Any kind of note for passengers")
    private = models.CharField(default=False)

    created_at = models.DateTimeField("date added", auto_now_add=True)

    def __str__(self):
        return f"From: {self.start}, Passengers: {self.dest_name}"

    # Very janky TEMPORARY system please someone replace it with a better one
    def schedule(self):
        schedule_string = ""
        if self.one_time:
            try:
                l_date = parser.parse(self.leaving_at_date_time)
                l_date_datetime = datetime.strptime(str(l_date), "%Y-%m-%d %H:%M:%S")
                l_date_formatted = datetime.strftime(l_date_datetime, "%d.%m.%Y  %H:%M")

                r_date = parser.parse(self.leaving_at_date_time)
                r_date_datetime = datetime.strptime(str(r_date), "%Y-%m-%d %H:%M:%S")
                r_date_formatted = datetime.strftime(r_date_datetime, "%d.%m.%Y  %H:%M")
            except ParserError:
                l_date_formatted = ""
                r_date_formatted = ""

            if self.one_way:
                
                schedule_string = l_date_formatted
            else:
                
                schedule_string = f"{l_date_formatted}\n{r_date_formatted}"
        else:
            day_filter = [
                self.monday_check, 
                self.tuesday_check, 
                self.wednesday_check, 
                self.thursday_check, 
                self.friday_check, 
                self.saturday_check, 
                self.sunday_check
            ]

            days = [
                _("Mon"), 
                _("Tue"), 
                _("Wed"), 
                _("Thu"), 
                _("Fri"), 
                _("Sat"), 
                _("Sun")
            ]

            schedule_string = ", ".join(compress(days, day_filter))
            # schedule_string = day_filter.join(", ")

        return schedule_string

    def sign(self):
        if self.one_way:
            return "→"
        else:
            return "⇄"

def to_string(self):
    l = ""
    for var_name, var_val in vars(self).items():
        l += f"{var_name}: {var_val}\n"
    return l
