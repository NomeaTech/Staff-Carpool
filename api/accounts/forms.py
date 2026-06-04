from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AdminUserCreationForm
from .models import User
from django import forms
from test_app.models import Address

class AddressForm(forms.ModelForm):
    model = Address
    # finish later

class CustomUserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = UserCreationForm.Meta.fields + (
            "username",
            "email",
            "first_name",
            "last_name",
        )
        
        # fields = UserCreationForm.Meta.fields + 
        # + AddressForm.Meta.fields

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
        )
        # fields = UserChangeForm.Meta.fields