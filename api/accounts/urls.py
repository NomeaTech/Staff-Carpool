from django.conf import settings
from django.contrib.auth.views import PasswordResetView
from django.urls import path
from .forms import ThrottledPasswordResetForm
from .views import SignUpView, UserLoginView, account, photo, confirmation_sent, resend_confirmation, confirm_email, confirm_email_change, login_code, cancel_login_code, two_factor_setup, backup_codes

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path("confirm/", confirmation_sent, name="confirmation_sent"),
    path("confirm/resend/", resend_confirmation, name="resend_confirmation"),
    path("confirm/<uidb64>/<token>/", confirm_email, name="confirm_email"),
    path("email/<uidb64>/<token>/", confirm_email_change, name="confirm_email_change"),
    path('login/', UserLoginView.as_view(), name='login'),
    path("login/code/", login_code, name="login_code"),
    path("login/code/cancel/", cancel_login_code, name="cancel_login_code"),
    path("two-step/", two_factor_setup, name="two_factor_setup"),
    path("two-step/backup-codes/", backup_codes, name="backup_codes"),
    path("profile/", account, name="account"),
    path("photo/<uuid:user_id>/", photo, name="user_photo"),
    # The reset email links to SITE_URL (e.g. https://kyyti.net) when it is set.
    # Logging out is Django's (django.contrib.auth.urls), which only logs out
    # on a POST, so a link on another site cannot log users out.
    path(
        "password_reset/",
        PasswordResetView.as_view(form_class=ThrottledPasswordResetForm, extra_email_context={"site_url": settings.SITE_URL}),
        name="password_reset",
    ),

]