"""
What members can see of each other.

- Everyone signed in sees a member's name as the member chose
  (User.name_visibility, by default "Aino M.") and their photo if they
  allow it (User.show_photo).
- People sharing a ride, i.e. its driver and its accepted passengers, are
  ride partners. Partners see each other's full names, and the contact
  details each has chosen to share (User.share_email, User.share_phone).
  Passengers are partners of the driver, not of each other.
- Email addresses and phone numbers are never shown anywhere else.

Views decide who is a partner and pass that on; templates use the
display_name filter and avatar tag in accounts/templatetags/privacy.py.
"""


def display_name(user, partner=False):
    if partner or user.name_visibility == user.NameVisibility.FULL:
        return f"{user.first_name} {user.last_name}".strip()
    if user.name_visibility == user.NameVisibility.FIRST or not user.last_name:
        return user.first_name
    return f"{user.first_name} {user.last_name[0]}."


def can_see_photo(user, viewer):
    return bool(user.pfp) and (user.show_photo or user == viewer)


def contact_details(user):
    """The contact details a member shares with their ride partners."""
    details = []
    if user.share_email and user.email:
        details.append(("email", user.email))
    if user.share_phone and user.phone:
        details.append(("phone", user.phone))
    return details

