from django.apps import AppConfig


class GroupsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "groups"

    def ready(self):
        # Keeping every group with an admin who can act (groups/services.py)
        from . import signals  # noqa: F401
