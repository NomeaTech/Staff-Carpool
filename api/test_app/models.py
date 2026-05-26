from django.db import models

class Address(models.Model):
    country = models.CharField(max_length=200)
    city = models.CharField(max_length=200)
    postcode = models.CharField(max_length=200)
    street = models.CharField(max_length=200)
    number = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.country}, {self.city}, {self.postcode}, {self.street} {self.number}"

class User(models.Model):
    password = models.CharField(max_length=200)
    first_name = models.CharField(max_length=200)
    last_name = models.CharField(max_length=200)
    pfp = models.ImageField(upload_to='static/images/')
    address = models.ForeignKey(Address, on_delete=models.CASCADE)
    date_joined = models.DateTimeField("date added")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Recurring_Trip(models.Model):
    driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="driver")
    passenger = models.ForeignKey(User, on_delete=models.CASCADE, related_name="passenger")
    private = models.BooleanField()
    start = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="start")
    destination = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="destination")
    created_at = models.DateTimeField("date added")

    def __str__(self):
        return f"Driver: {self.driver}, Passenger: {self.passenger}"

def to_string(self):
    l = ""
    for var_name, var_val in vars(self).items():
        l += f"{var_name}: {var_val}\n"
    return l
