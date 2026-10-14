from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


def find_user(email):
    """
    The user with the email address, ignoring upper and lower case, so that
    e.g. Jamie.Saarinen@lut.fi and jamie.saarinen@lut.fi are the same account.
    None if there is none, or (for addresses saved before this was checked)
    several that differ only in case and none matching exactly.
    """
    UserModel = get_user_model()
    users = list(UserModel.objects.filter(email__iexact=email or "")[:2])
    if len(users) == 1:
        return users[0]
    return next((user for user in users if user.email == email), None)


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = find_user(username)
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        # Blocked accounts (is_active) and accounts whose email address has
        # not been confirmed (accounts/confirmation.py) cannot log in. Also
        # checked for logged in users on every request (get_user).
        return super().user_can_authenticate(user) and user.email_confirmed_at is not None
