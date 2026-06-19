from django.db import models
from django.conf import settings
from datetime import datetime

class Address(models.Model):
    country = models.CharField(max_length=200)
    city = models.CharField(max_length=200)
    postcode = models.CharField(max_length=200)
    street = models.CharField(max_length=200)
    number = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.country}, {self.city}, {self.postcode}, {self.street} {self.number}"

class Recurring_Trip(models.Model):
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="driver"
    )

    passenger = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name="passenger"
    )
    
    private = models.BooleanField()
    max_passengers = models.IntegerField()
    start = models.ForeignKey('test_app.Address', on_delete=models.CASCADE, related_name="start")
    destination = models.ForeignKey('test_app.Address', on_delete=models.CASCADE, related_name="destination")
    # leaving_at = models.DateTimeField("time car leaves")#, default=datetime.strptime("1, 00:00 (1900)","%-d, %H:%M (%Y)"))
    # arriving_at = models.DateTimeField("time car arrives")#, default=datetime.strptime("1, 00:00 (1900)","%-d, %H:%M (%Y)"))
    
    WEEKDAY_CHOICES = (
        ("Monday", "monday"),
        ("Tuesday","tuesday"),
        ("Wednesday","wednesday"),
        ("Thursday","thursday"),
        ("Friday","friday"),
        ("Saturday","saturday"),
        ("Sunday","sunday"),
        ("Weekdays", "weekdays"),
        ("Weekends", "weekends")
    )

    leaving_at_weekday = models.CharField(max_length=10, choices=WEEKDAY_CHOICES)
    leaving_at_hour = models.IntegerField()
    leaving_at_minute = models.IntegerField()

    arriving_at_weekday = models.CharField(max_length=10, choices=WEEKDAY_CHOICES)
    arriving_at_hour = models.IntegerField()
    arriving_at_minute = models.IntegerField()

    note = models.TextField(blank=True, default="", help_text="Any kind of note for passengers")
    destName = models.CharField(help_text="Destination name")

    created_at = models.DateTimeField("date added", auto_now_add=True)

    def __str__(self):
        passengers = ", ".join([ str(p) for p in self.passenger.all() ])
        return f"Driver: {self.driver}, Passengers: {passengers}"

def to_string(self):
    l = ""
    for var_name, var_val in vars(self).items():
        l += f"{var_name}: {var_val}\n"
    return l
