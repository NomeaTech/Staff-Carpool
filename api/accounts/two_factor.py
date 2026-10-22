"""
Two-step verification: logging in also needs a code from an authenticator
app (Google Authenticator, Microsoft Authenticator, a password manager...),
so that a password alone is not enough. Users choose to turn it on, on the
profile page; the admin needs it (carpool/admin_site.py).

- Turning it on (two_factor_setup): the page shows a QR code to scan, a
  link that opens the authenticator app on a phone, and the key to type in
  by hand. It is on once a code from the app is entered, which proves the
  app was set up. The key is kept (as an unconfirmed device) until then, so
  reloading the page does not change the QR code already scanned.
- Backup codes: BACKUP_CODES codes that work once each, for when the phone
  is lost. They are shown once, when it is turned on or new ones are made.
- Logging in (UserLoginView): with the right password, the user is not yet
  logged in. Who they are is kept in the session for LOGIN_TIMEOUT, and the
  next page asks for the code (login_code).
- Wrong codes: after each one, django-otp makes the user wait longer before
  the next try (1, 2, 4, 8... seconds), so codes cannot be guessed.
- If a user loses their phone and their backup codes, an admin deletes the
  user's devices in the admin (OTP_TOTP/OTP_STATIC), which turns it off.

The devices are django-otp's: a TOTPDevice for the app and a StaticDevice
for the backup codes. django-otp's middleware gives request.user.is_verified().
"""
import math
import time
from base64 import b32encode
from urllib.parse import quote, urlencode

import segno
from django.contrib.auth import login
from django.db import transaction
from django.utils import timezone
from django_otp import login as otp_login
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

# The name in the authenticator app, above the user's email address
ISSUER = "LUT Kyyti"
BACKUP_CODES = 10
# How long after entering the password the code can be entered
LOGIN_TIMEOUT = 10 * 60
SESSION_KEY = "two_factor_login"


def enabled(user):
    return TOTPDevice.objects.filter(user=user, confirmed=True).exists()


def backup_codes_left(user):
    return StaticToken.objects.filter(device__user=user, device__confirmed=True).count()


# Turning on

def setup_device(user):
    """The device being set up, with the key the setup page shows."""
    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    return device or TOTPDevice.objects.create(user=user, name="Authenticator app", confirmed=False)


def setup_url(device):
    """The otpauth:// link that adds the account to an authenticator app, also shown as the QR code."""
    label = quote(f"{ISSUER}:{device.user.email}")
    params = urlencode({"secret": secret(device), "issuer": ISSUER, "digits": device.digits, "period": device.step})
    return f"otpauth://totp/{label}?{params}"


def qr_code(url):
    """The link as an inline SVG QR code. It scales to the size of its box."""
    return segno.make(url, error="m").svg_inline(scale=1, border=0, omitsize=True, dark="#000")


def secret(device):
    return b32encode(device.bin_key).decode()


def grouped(key):
    """The key in groups of four letters, for typing it in by hand."""
    return " ".join(key[i:i + 4] for i in range(0, len(key), 4))


def confirm(request, device, code):
    """
    Turns two-step verification on, if code is the app's current code.
    Returns (backup codes, wait): the new backup codes, or None for a wrong
    code and the seconds to wait as for check_code. The session counts as
    verified, so the user is not asked for a code again.
    """
    with transaction.atomic():
        device = TOTPDevice.objects.select_for_update().get(pk=device.pk)
        accepted, wait = verify(device, normalise(code))
    if not accepted:
        return None, wait
    device.confirmed = True
    device.save(update_fields=["confirmed"])
    TOTPDevice.objects.filter(user=device.user, confirmed=False).delete()
    codes = new_backup_codes(device.user)
    otp_login(request, device)
    return codes, 0


def new_backup_codes(user):
    """Replaces the user's backup codes with BACKUP_CODES new ones, and returns them."""
    with transaction.atomic():
        StaticDevice.objects.filter(user=user).delete()
        device = StaticDevice.objects.create(user=user, name="Backup codes")
        codes = [StaticToken.random_token() for _ in range(BACKUP_CODES)]
        StaticToken.objects.bulk_create(StaticToken(device=device, token=code) for code in codes)
    return codes


def turn_off(user):
    TOTPDevice.objects.filter(user=user).delete()
    StaticDevice.objects.filter(user=user).delete()


def show_code(code):
    """A backup code as shown to the user, e.g. "k3d9-x2mq"."""
    return f"{code[:4]}-{code[4:]}"


# Logging in

def normalise(code):
    """The code without the spaces and dashes people type in it."""
    return "".join(code.split()).replace("-", "").lower()


def check_code(user, code):
    """
    (device, wait): the device that accepts code (from the app, or a backup
    code), or None and, after too many wrong codes, how many seconds the
    user must wait before trying again (0 otherwise).
    """
    code = normalise(code)
    model = TOTPDevice if code.isdigit() else StaticDevice
    with transaction.atomic():
        device = model.objects.filter(user=user, confirmed=True).select_for_update().first()
        if device is None:
            return None, 0
        accepted, wait = verify(device, code)
    return (device if accepted else None), wait


def verify(device, code):
    """(accepted, wait): whether device accepts code, and if it was not tried
    because of too many wrong codes, how many seconds are left to wait."""
    allowed, details = device.verify_is_allowed()
    if not allowed:
        locked_until = (details or {}).get("locked_until")
        wait = (locked_until - timezone.now()).total_seconds() if locked_until else 1
        return False, max(1, math.ceil(wait))
    return device.verify_token(code), 0


def begin_login(request, user, next_url):
    """The password was right: keeps who is logging in until the code is entered."""
    request.session[SESSION_KEY] = {
        "user": str(user.pk),
        "backend": user.backend,
        "next": next_url,
        "at": time.time(),
    }


def pending_login(request):
    """The session's login waiting for a code, or None if there is none or it timed out."""
    pending = request.session.get(SESSION_KEY)
    if not pending or time.time() - pending["at"] > LOGIN_TIMEOUT:
        return None
    return pending


def cancel_login(request):
    request.session.pop(SESSION_KEY, None)


def finish_login(request, user, device, backend):
    cancel_login(request)
    login(request, user, backend=backend)
    otp_login(request, device)
