from django.urls import path
from .views import SignUpView, LogoutView, UserLoginView

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path('login/', UserLoginView.as_view(), name='login'),
    path("logout", LogoutView, name="logout"),

]