from django.urls import path

from . import views

urlpatterns = [
    path("", views.notification_list, name="notifications"),
    path("menu/", views.menu, name="notifications_menu"),
    path("poll/", views.poll, name="notifications_poll"),
    path("read/", views.mark_all_read, name="notifications_mark_all_read"),
    path("<uuid:notification_id>/", views.open_notification, name="open_notification"),
]
