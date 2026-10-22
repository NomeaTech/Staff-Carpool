from django.urls import path

from .views import group_detail, group_list

urlpatterns = [
    path("", group_list, name="groups"),
    path("<uuid:group_id>/", group_detail, name="group_detail"),
]
