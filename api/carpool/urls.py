"""
URL configuration for carpool project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.templatetags.static import static
from django.views.generic import RedirectView

from .health import health

urlpatterns = [
    # For the deploys' health checks (carpool/health.py)
    path('healthz', health),
    path('admin/', admin.site.urls),
    path('rosetta/', include('rosetta.urls')),
    path('app/', include('home.urls')),
    path("i18n/", include("django.conf.urls.i18n")),
    path('', include('landing.urls')),
    path('', include('pwa.urls')),
    # Browsers and other tools ask for /favicon.ico when a page names no icon
    path('favicon.ico', RedirectView.as_view(url=static('images/icons/favicon.ico'), permanent=True)),
]
# The error pages, in the site's look (carpool/errors.py)
handler400 = "carpool.errors.bad_request"
handler403 = "carpool.errors.permission_denied"
handler404 = "carpool.errors.page_not_found"
handler500 = "carpool.errors.server_error"
