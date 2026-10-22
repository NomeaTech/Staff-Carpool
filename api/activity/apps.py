from django.apps import AppConfig


class ActivityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "activity"

    def ready(self):
        # Logins and logouts (activity/events.py)
        from . import events  # noqa: F401
