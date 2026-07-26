from django.db import models
# from test_app.models import Address
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Remove username without actually removing it
    username = models.CharField(null=True, blank=True)
    email = models.EmailField(unique=True)

    pfp = models.ImageField(upload_to='static/images/', blank=True, null=True)
    address = models.ForeignKey('test_app.Address', on_delete=models.CASCADE, null=True, blank=True)
    rides = models.ManyToManyField('test_app.Ride', blank=True)
    phone = models.CharField(blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"