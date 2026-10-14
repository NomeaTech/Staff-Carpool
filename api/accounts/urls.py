from django.conf import settings
from django.contrib.auth.views import PasswordResetView
from django.urls import path
from .views import SignUpView, LogoutView, UserLoginView, account, photo

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
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