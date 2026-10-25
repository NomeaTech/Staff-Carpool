from django.urls import path

from . import views

urlpatterns = [
    path("", views.notification_list, name="notifications"),
    path("menu/", views.menu, name="notifications_menu"),
    path("poll/", views.poll, name="notifications_poll"),
    path("read/", views.mark_all_read, name="notifications_mark_all_read"),
    path("push/subscribe/", views.push_subscribe, name="push_subscribe"),
    path("push/unsubscribe/", views.push_unsubscribe, name="push_unsubscribe"),
    path("<uuid:notification_id>/", views.open_notification, name="open_notification"),
]
