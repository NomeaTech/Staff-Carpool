from django.conf import settings
from django.contrib.auth.views import PasswordResetView
from django.urls import path
from .views import SignUpView, LogoutView, UserLoginView, account, photo, confirmation_sent, resend_confirmation, confirm_email, confirm_email_change

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path("confirm/", confirmation_sent, name="confirmation_sent"),
    path("confirm/resend/", resend_confirmation, name="resend_confirmation"),
    path("confirm/<uidb64>/<token>/", confirm_email, name="confirm_email"),
    path("email/<uidb64>/<token>/", confirm_email_change, name="confirm_email_change"),
    path('login/', UserLoginView.as_view(), name='login'),
    path("logout", LogoutView, name="logout"),
    path("profile/", account, name="account"),
    path("photo/<uuid:user_id>/", photo, name="user_photo"),
    # The reset email links to SITE_URL (e.g. https://kyyti.net) when it is set
    path(
        "password_reset/",
        PasswordResetView.as_view(extra_email_context={"site_url": settings.SITE_URL}),
        name="password_reset",
    ),

]