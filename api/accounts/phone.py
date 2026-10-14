"""
Phone numbers, checked with the phonenumbers library (Google's
libphonenumber). Numbers without a country code are taken to be Finnish.
They are stored in E.164 format ("+358401234567") and shown in the
international format ("+358 40 1234567").
"""
import phonenumbers

DEFAULT_REGION = "FI"


def parse(value):
    """The number as a PhoneNumber if it is a possible, valid number, otherwise None."""
    try:
        number = phonenumbers.parse(value, DEFAULT_REGION)
    except phonenumbers.NumberParseException:
        return None
    return number if phonenumbers.is_valid_number(number) else None


def to_e164(number):
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def display(value):
    """A stored number for showing, or the value as it is if it cannot be read."""
    number = parse(value or "")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL) if number else value
