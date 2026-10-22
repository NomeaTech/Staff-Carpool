from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AdminUserCreationForm, AuthenticationForm, UsernameField
from .models import User
from .backends import find_user
from . import email_change
from . import phone as phone_numbers
from django.db import models
from django import forms
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

# Only LUT and LAB addresses can sign up or be changed to
ALLOWED_EMAIL_DOMAINS = ("lut.fi", "lab.fi")
# Shown in messages, outside the translated text (gettext warns about addresses in it)
EXAMPLE_EMAIL = "firstname.lastname@lut.fi"
# The same in the browser (the pattern attribute has no case-insensitive flag)
EMAIL_PATTERN = r"[^@\s]+@([Ll][Uu][Tt]|[Ll][Aa][Bb])\.[Ff][Ii]"
# Passwords: at least 8 characters (MinimumLengthValidator), with a number, a
# lower case and an upper case letter (accounts.validators.CharacterMixValidator)
PASSWORD_MIN_LENGTH = 8
PASSWORD_PATTERN = r"(?=.*\p{Nd})(?=.*\p{Ll})(?=.*\p{Lu}).{8,}"
NAME_MAX_LENGTH = 50

def email_domain_allowed(email):
    return email.rsplit("@", 1)[-1].lower() in ALLOWED_EMAIL_DOMAINS

class CustomUserCreationForm(AdminUserCreationForm):
    error_messages = {
        **AdminUserCreationForm.error_messages,
        "password_mismatch": _("The passwords don't match. Type the same password in both fields."),
    }

    def __init__(self, *args, **kwargs):
        super(AdminUserCreationForm, self).__init__(*args, **kwargs)

    def validate_password_for_user(self, user, **kwargs):
        # What is wrong with the password is shown under the password field,
        # not under "confirm password" as Django does
        kwargs["password_field_name"] = "password1"
        super().validate_password_for_user(user, **kwargs)

    email = forms.EmailField(
        max_length=254,
        help_text=_('Required. Enter a valid email address.'),
        error_messages={
            "required": _("Enter your LUT or LAB email address."),
            "invalid": format_lazy(_("Enter a valid email address, e.g. {example}."), example=EXAMPLE_EMAIL),
        },
        widget=forms.EmailInput(attrs={
            'class': 'input validator w-full',
            'placeholder': _("Email Address *"),
            'autocomplete': 'email',
            'pattern': EMAIL_PATTERN,
            'title': _("Your LUT or LAB email address, ending in @lut.fi or @lab.fi"),
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
        max_length=NAME_MAX_LENGTH,
        error_messages={
            "required": _("Enter your first name."),
            "max_length": _("Your first name can be at most %(limit_value)s characters."),
        },
        widget=forms.TextInput(
            attrs={
                'class': 'input validator col-span-3 w-full',
                'placeholder': _("First Name *"),
                'autocomplete': 'given-name',
            }
        )
    )

    last_name = forms.CharField(
        max_length=NAME_MAX_LENGTH,
        error_messages={
            "required": _("Enter your last name."),
            "max_length": _("Your last name can be at most %(limit_value)s characters."),
        },
        widget=forms.TextInput(
            attrs={
                'class': 'input validator col-span-3 w-full',
                'placeholder': _("Last Name *"),
                'autocomplete': 'family-name',
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
        strip=False,
        error_messages={"required": _("Choose a password.")},
        widget=forms.PasswordInput(
            attrs={
                'class': 'input validator col-span-3 w-full',
                'placeholder': _("Password *"),
                'autocomplete': 'new-password',
                'minlength': PASSWORD_MIN_LENGTH,
                'pattern': PASSWORD_PATTERN,
                'title': _("At least 8 characters, including a number, a lower case letter and an upper case letter"),
            }
        )
    )

    password2 = forms.CharField(
        strip=False,
        error_messages={"required": _("Type your password again to confirm it.")},
        widget=forms.PasswordInput(
            attrs={
                'class': 'input validator col-span-3 w-full',
                'placeholder': _("Confirm Password *"),
                'autocomplete': 'new-password',
                'title': _("The same password again"),
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

    # An account with the email address that was never confirmed. SignUpView
    # sends its confirmation link again.
    unconfirmed_user = None

    def clean_email(self):
        # Saved in lower case: addresses are not case-sensitive in practice
        email = self.cleaned_data["email"].strip().lower()
        if not email_domain_allowed(email):
            raise forms.ValidationError(
                _("Use your LUT or LAB email address (ending in @lut.fi or @lab.fi)."), code="domain",
            )
        existing = User.objects.filter(email__iexact=email).first()
        if existing and existing.email_confirmed_at is None:
            self.unconfirmed_user = existing
            raise forms.ValidationError(
                _("This email address has already signed up but has not been confirmed yet. We have sent the confirmation link again."),
                code="unconfirmed",
            )
        if existing:
            raise forms.ValidationError(
                _("An account with this email address already exists. Log in, or reset your password if you have forgotten it."),
                code="unique",
            )
        return email

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
    # The email address when the password is right but the address has not
    # been confirmed, so that the login page can offer a new link
    unconfirmed_email = None

    def __init__(self, *args, **kwargs):
        super(UserLoginForm, self).__init__(*args, **kwargs)

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError:
            # Only with the right password, so that it does not tell anyone
            # else whether the address has an account
            email, password = self.cleaned_data.get("username"), self.cleaned_data.get("password")
            user = find_user(email) if email else None
            if user and user.is_active and user.email_confirmed_at is None and user.check_password(password):
                self.unconfirmed_email = user.email
                raise forms.ValidationError(
                    _("Confirm your email address before logging in. Open the link we sent to %(email)s.") % {"email": user.email},
                    code="unconfirmed",
                )
            raise

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
    phone = forms.CharField(required=False, max_length=30)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Shown spaced out, e.g. "+358 40 1234567"
        if self.instance.phone:
            self.initial["phone"] = phone_numbers.display(self.instance.phone)

    def clean_phone(self):
        value = self.cleaned_data["phone"].strip()
        if not value:
            return None
        number = phone_numbers.parse(value)
        if number is None:
            raise forms.ValidationError(
                _("Enter a valid phone number, e.g. 040 123 4567 or +358 40 123 4567. Include the country code for numbers outside Finland."),
                code="invalid",
            )
        return phone_numbers.to_e164(number)


class SettingsForm(forms.ModelForm):
    """Privacy and notification settings, see accounts/privacy.py."""
    class Meta:
        model = User
        fields = ("name_visibility", "show_photo", "share_email", "share_phone", "email_notifications")
        widgets = {
            "name_visibility": forms.RadioSelect(attrs={"class": "radio radio-primary radio-sm"}),
            "email_notifications": forms.RadioSelect(attrs={"class": "radio radio-primary radio-sm"}),
        }


# Larger photos are refused. The profile page also checks this before
# uploading (photo_too_large), as Nginx refuses requests over 100 MB with its
# own error page, before they reach the app.
PHOTO_MAX_UPLOAD = 10 * 1024 * 1024

def photo_too_large():
    return _("The photo must be smaller than %(size)s MB.") % {"size": PHOTO_MAX_UPLOAD // (1024 * 1024)}

class PhotoForm(forms.Form):
    photo = forms.ImageField()
    # The square the user framed their face in (see account.html). Without
    # it, e.g. when JavaScript is off, the middle of the photo is used.
    crop_x = forms.FloatField(required=False, widget=forms.HiddenInput)
    crop_y = forms.FloatField(required=False, widget=forms.HiddenInput)
    crop_size = forms.FloatField(required=False, min_value=1, widget=forms.HiddenInput)

    def clean_photo(self):
        photo = self.cleaned_data["photo"]
        if photo.size > PHOTO_MAX_UPLOAD:
            raise forms.ValidationError(photo_too_large())
        return photo

    def save(self, user):
        # User.save() shrinks the photo and names it with a UUID
        data = self.cleaned_data
        crop = (data["crop_x"], data["crop_y"], data["crop_size"])
        user.pfp = data["photo"]
        user.pfp_crop = crop if None not in crop else None
        user.save(update_fields=["pfp"])


class PasswordConfirmForm(forms.Form):
    """The user's password, to confirm something done on the profile page."""
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError(_("The password is incorrect."))
        return password


class DeleteAccountForm(PasswordConfirmForm):
    pass


class CodeForm(forms.Form):
    """A code from the authenticator app, or a backup code (accounts/two_factor.py)."""
    code = forms.CharField(
        max_length=20,
        error_messages={"required": _("Enter the code.")},
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "autocapitalize": "off", "spellcheck": "false"}),
    )


class EmailChangeForm(forms.Form):
    """Asks to change the account's email address (accounts/email_change.py)."""
    new_email = forms.EmailField(max_length=254)
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_new_email(self):
        # Saved in lower case: addresses are not case-sensitive in practice
        email = self.cleaned_data["new_email"].strip().lower()
        if not email_domain_allowed(email):
            raise forms.ValidationError(_("Use your LUT or LAB email address (ending in @lut.fi or @lab.fi)."), code="domain")
        if email == self.user.email.lower():
            raise forms.ValidationError(_("This is already your email address."), code="same")
        if email_change.address_taken(email, self.user):
            raise forms.ValidationError(_("Another account already uses this email address."), code="taken")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError(_("The password is incorrect."), code="password")
        return password
