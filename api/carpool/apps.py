from django.contrib.admin.apps import AdminConfig as BaseAdminConfig
from django.contrib.staticfiles.apps import StaticFilesConfig as BaseStaticFilesConfig


class AdminConfig(BaseAdminConfig):
    # Needs two-step verification
    default_site = "carpool.admin_site.AdminSite"


class StaticFilesConfig(BaseStaticFilesConfig):
    # Profile photos were once saved in static/images/user_images/. Anyone
    # could download them from there, whatever the user chose to show, so
    # collectstatic leaves them out; accounts.views.photo serves them.
    ignore_patterns = [*BaseStaticFilesConfig.ignore_patterns, "user_images"]
