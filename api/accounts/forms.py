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
        help_text=_('Required. Enter a valid email address.'),
        widget=forms.EmailInput(attrs={
            'class': 'input validator w-full',
            'placeholder': _("Email Address *"),
            'autocomplete': 'email',
            'pattern': '.*@(lab|lut)\.fi',
        })
    )

    username = UsernameField(required=False, widget=forms.TextInput(
        attrs={
                'class': 'hidden input validator col-span-3 w-full', 
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
        required=False,
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
                'autocomplete': 'new-password',
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
                'autocomplete': 'new-password',
                'type': 'password',
                'minlength': 8,
                'pattern': '(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,}',
                'title': _('Must be more than 8 characters, including number, lowercase letter, uppercase letter *'),
            }
        )
    )

    # Don't forget to implement the view for this otherwise file upload will not work :)
    pfp = forms.ImageField(
        required=False,
        widget=forms.FileInput(
            attrs={
                'class': 'file-input file-input-info col-span-3 w-full',
            }
        )
    )
    
    class Meta:
        model = User
        fields = UserCreationForm.Meta.fields + (
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
            "phone",
            "pfp",
        )
        
        # fields = UserCreationForm.Meta.fields + 
        # + AddressForm.Meta.fields

class SignUpForm(CustomUserCreationForm):
    """The sign up page's form: the admin's user creation form without the
    phone number and profile picture."""
    phone = None
    pfp = None

    class Meta(CustomUserCreationForm.Meta):
        fields = tuple(f for f in CustomUserCreationForm.Meta.fields if f not in ("phone", "pfp"))

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
        )
        # fields = UserChangeForm.Meta.fields

class UserLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super(UserLoginForm, self).__init__(*args, **kwargs)

    username = forms.EmailField(widget=forms.EmailInput(
        attrs={
                'class': 'input validator col-span-3 w-full', 
                'placeholder': _("Email"),
                'autocomplete': 'email',
                'name': 'email',
            }
        )
    )

    # email = forms.EmailField(widget=forms.TextInput(
    #     attrs={
    #             'class': 'input validator col-span-3 w-full', 
    #             'placeholder': _("Email")
    #         }
    #     )
    # )
    
    password = forms.CharField(widget=forms.PasswordInput(
        attrs={
            'class': 'input validator col-span-3 w-full',
            'placeholder': _("Password"),
        }
    )
)

class ProfileForm(forms.ModelForm):
    """Personal information on the profile & settings page. The email address
    identifies the account and is not changed here."""
    phone = forms.RegexField(
        required=False,
        regex=r"^\+?[0-9 ]{6,20}$",
        error_messages={"invalid": _("Enter a phone number using digits, e.g. +358 40 123 4567.")},
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone")

    def clean_phone(self):
        return self.cleaned_data["phone"].replace(" ", "") or None


class SettingsForm(forms.ModelForm):
    """Privacy and notification settings, see accounts/privacy.py."""
    class Meta:
        model = User
        fields = ("name_visibility", "show_photo", "share_email", "share_phone", "notify_ride_requests")
        widgets = {"name_visibility": forms.RadioSelect(attrs={"class": "radio radio-primary radio-sm"})}


PHOTO_MAX_UPLOAD = 10 * 1024 * 1024

class PhotoForm(forms.Form):
    photo = forms.ImageField()

    def clean_photo(self):
        photo = self.cleaned_data["photo"]
        if photo.size > PHOTO_MAX_UPLOAD:
            raise forms.ValidationError(_("The photo must be smaller than 10 MB."))
        return photo

    def save(self, user):
        # User.save() shrinks the photo and names it with a UUID
        user.pfp = self.cleaned_data["photo"]
        user.save(update_fields=["pfp"])


class DeleteAccountForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError(_("The password is incorrect."))
        return password
