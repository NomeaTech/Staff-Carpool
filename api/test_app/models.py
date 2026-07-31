from django.db import models
from django_geoaddress.fields import GeoaddressField
from django.conf import settings
from datetime import datetime
from django.contrib.postgres.fields import ArrayField

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
    test = GeoaddressField()

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="driver"
    )

    passenger = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name="passenger"
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

    leaving_at_date = models.CharField(blank=True)
    leaving_at_time = models.CharField(blank=True)
    # leaving_at_hour = models.IntegerField(blank=True)
    # leaving_at_minute = models.IntegerField(blank=True)

    arriving_at_date = models.CharField(blank=True)
    arriving_at_time = models.CharField(blank=True)
    # arriving_at_hour = models.IntegerField(blank=True)
    # arriving_at_minute = models.IntegerField(blank=True)

    # Recurring days

    mo_leaving_at_time = models.CharField(blank=True)
    mo_arriving_at_time = models.CharField(blank=True)
    
    tu_leaving_at_time = models.CharField(blank=True)
    tu_arriving_at_time = models.CharField(blank=True)
    
    we_leaving_at_time = models.CharField(blank=True)
    we_arriving_at_time = models.CharField(blank=True)
    
    th_leaving_at_time = models.CharField(blank=True)
    th_arriving_at_time = models.CharField(blank=True)
    
    fr_leaving_at_time = models.CharField(blank=True)
    fr_arriving_at_time = models.CharField(blank=True)
    
    sa_leaving_at_time = models.CharField(blank=True)
    sa_arriving_at_time = models.CharField(blank=True)
    
    su_leaving_at_time = models.CharField(blank=True)
    su_arriving_at_time = models.CharField(blank=True)

    note = models.TextField(blank=True, default="", help_text="Any kind of note for passengers")
    private = models.CharField(default=False)

    created_at = models.DateTimeField("date added", auto_now_add=True)
    
    # private = models.BooleanField()
    # start = models.ForeignKey('test_app.Address', on_delete=models.CASCADE, related_name="start")
    # destination = models.ForeignKey('test_app.Address', on_delete=models.CASCADE, related_name="destination")
    # leaving_at = models.DateTimeField("time car leaves")#, default=datetime.strptime("1, 00:00 (1900)","%-d, %H:%M (%Y)"))
    # arriving_at = models.DateTimeField("time car arrives")#, default=datetime.strptime("1, 00:00 (1900)","%-d, %H:%M (%Y)"))
    
    # WEEKDAY_CHOICES = (
    #     ("Monday", "monday"),
    #     ("Tuesday","tuesday"),
    #     ("Wednesday","wednesday"),
    #     ("Thursday","thursday"),
    #     ("Friday","friday"),
    #     ("Saturday","saturday"),
    #     ("Sunday","sunday"),
    # )

    def __str__(self):
        passengers = ", ".join([ str(p) for p in self.passenger.all() ])
        return f"Driver: {self.driver}, Passengers: {passengers}"

def to_string(self):
    l = ""
    for var_name, var_val in vars(self).items():
        l += f"{var_name}: {var_val}\n"
    return l
