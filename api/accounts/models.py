from django.db import models
from test_app.models import Address

class Profile(models.Model):
    pfp = models.ImageField(upload_to='static/images/')
    address = models.ForeignKey(Address, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"