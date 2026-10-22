from django.contrib.admin.apps import AdminConfig as BaseAdminConfig


class AdminConfig(BaseAdminConfig):
    # Needs two-step verification
    default_site = "carpool.admin_site.AdminSite"
