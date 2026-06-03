from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import User

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    list_display = [
        "email",
        "username",
        # "address",
    ]
    # fieldsets = UserAdmin.fieldsets + ((None, {"fields": ("address",)}),)
    # add_fieldsets = UserAdmin.add_fieldsets + ((None, {"fields": ("address",)}),)