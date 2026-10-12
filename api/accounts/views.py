from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import SignUpForm, UserLoginForm

class SignUpView(CreateView):
    form_class = SignUpForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"

class UserLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = UserLoginForm
    # Users who are already logged in skip the login page. They are sent to
    # ?next= if it is a safe URL, otherwise to LOGIN_REDIRECT_URL (/app/home/).
    redirect_authenticated_user = True

    def get_redirect_url(self):
        # Only follow ?next= to pages in the app, e.g. a shared ride. Logging
        # in from the landing pages (?next=/, /faq, ...) goes to /app/home/.
        url = super().get_redirect_url()
        return url if url.startswith("/app/") else ""

def LogoutView(request):
    logout(request)