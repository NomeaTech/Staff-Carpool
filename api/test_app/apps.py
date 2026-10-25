from django.apps import AppConfig


class TestAppConfig(AppConfig):
    """
    Only the migrations of the app the rides started in remain: older accounts
    and notifications migrations depend on them. Its models are now in the
    rides app, which took over their tables (test_app 0045 and rides 0001).
    """
    name = 'test_app'
