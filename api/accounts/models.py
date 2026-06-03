from django.db import models
# from test_app.models import Address
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    pfp = models.ImageField(upload_to='static/images/')
    # address = models.ForeignKey('test_app.Address', on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"