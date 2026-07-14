from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AdminUserCreationForm, AuthenticationForm, UsernameField
from .models import User
from django.db import models
from django import forms
from django.utils.translation import gettext_lazy as _

class CustomUserCreationForm(AdminUserCreationForm):
    def __init__(self, *args, **kwargs):
        super(AdminUserCreationForm, self).__init__(*args, **kwargs)

    email = forms.EmailField(
        max_length=254,
        required=True,
        help_text=_('Required. Enter a valid email address.'),
        widget=forms.EmailInput(attrs={
            'class': 'input validator w-full',
            'placeholder': _("Email Address *"),
            'pattern': '.*@(lab|lut)\.fi',
        })
    )

    username = UsernameField(widget=forms.TextInput(
        attrs={
                'class': 'input validator col-span-3 w-full', 
                'placeholder': _("Username"),
            }
        )
    )

    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(
            attrs={
                'class': 'input validator col-span-3 w-full',
                'placeholder': _("First Name *"),
            }
        )
    )

    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(
            attrs={
                'class': 'input validator col-span-3 w-full',
                'placeholder': _("Last Name *"),
            }
        )
    )

    phone = forms.CharField(
        max_length=14,
        min_length=10,
        widget=forms.TextInput(
            attrs={
                'class': 'input validator tabular-nums col-span-3 w-full',
                'type': 'tel',
                'placeholder': _("Phone"),
                'pattern': '[0-9]*'
            }
        )
    )

    password1 = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'class': 'input validator col-span-3 w-full',
                'placeholder': _("Password *"),
                'type': 'password',
                'minlength': 8,
                'pattern': '(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,}',
                'title': _('Must be more than 8 characters, including number, lowercase letter, uppercase letter'),
            }
        )
    )

    password2 = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'class': 'input validator col-span-3 w-full',
                'placeholder': _("Confirm Password *"),
                'type': 'password',
                'minlength': 8,
                'pattern': '(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,}',
                'title': _('Must be more than 8 characters, including number, lowercase letter, uppercase letter *'),
            }
        )
    )

    # Don't forget to implement the view for this otherwise file upload will not work :)
    pfp = forms.FileField(
        widget=forms.FileInput(
            attrs={
                'class': 'file-input file-input-info col-span-3 w-full',
            }
        )
    )
    
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