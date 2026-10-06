from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import CustomUserCreationForm, UserLoginForm

class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"

class UserLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = UserLoginForm
    # Users who are already logged in skip the login page. They are sent to
    # ?next= if it is a safe URL, otherwise to LOGIN_REDIRECT_URL (/app/home/).
    redirect_authenticated_user = True

def LogoutView(request):
    logout(request)