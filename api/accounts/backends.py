from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(email=username)
        except UserModel.DoesNotExist:
            return None
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None

    def user_can_authenticate(self, user):
        # Blocked accounts (is_active) and accounts whose email address has
        # not been confirmed (accounts/confirmation.py) cannot log in. Also
        # checked for logged in users on every request (get_user).
        return super().user_can_authenticate(user) and user.email_confirmed_at is not None
