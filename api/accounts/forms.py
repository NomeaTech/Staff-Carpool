from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AdminUserCreationForm
from .models import User
from django import forms
from django.utils.translation import gettext_lazy as _

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

# Source - https://stackoverflow.com/a/55369752
# Posted by Nakul Narayanan, modified by community. See post 'Timeline' for change history
# Retrieved 2026-06-27, License - CC BY-SA 4.0

from django.contrib.auth.forms import AuthenticationForm, UsernameField

from django import forms


class UserLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super(UserLoginForm, self).__init__(*args, **kwargs)

    username = UsernameField(widget=forms.TextInput(
        attrs={
                'class': 'input validator col-span-3 w-full', 
                'placeholder': _("Username")
            }
        )
    )
    password = forms.CharField(widget=forms.PasswordInput(
        attrs={
            'class': 'input validator col-span-3 w-full',
            'placeholder': _("Password"),
        }
    )
)
