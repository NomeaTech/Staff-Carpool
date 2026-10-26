import importlib
import os
from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase, TestCase

import carpool.settings as project_settings


class HealthCheckTests(TestCase):
    def test_ok(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertIn("no-cache", response["Cache-Control"])

    def test_unavailable_without_the_database(self):
        with patch("carpool.health.connection") as connection, self.assertLogs("carpool.health", "ERROR"):
            connection.cursor.side_effect = OperationalError("connection refused")
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503)

    def test_unknown_address_gets_the_400_page(self):
        # It stops before the login middleware, so the page has no user to show
        with self.assertLogs("django.security.DisallowedHost", "ERROR"):
            response = self.client.get("/healthz", headers={"host": "unknown.example"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "400", status_code=400)


class SettingsFromEnvironmentTests(SimpleTestCase):
    def reload(self, **environ):
        # os.environ keeps load_dotenv()'s values, so .env cannot override these
        with patch.dict(os.environ, environ):
            return importlib.reload(project_settings)

    def tearDown(self):
        importlib.reload(project_settings)

    def test_database_url(self):
        database = self.reload(DATABASE_URL="postgres://kyyti:p%40ss@db-1:6543/rides").DATABASES["default"]
        self.assertEqual(
            (database["NAME"], database["USER"], database["PASSWORD"], database["HOST"], database["PORT"]),
            ("rides", "kyyti", "p@ss", "db-1", "6543"),
        )

    def test_local_database_without_database_url(self):
        database = self.reload(DATABASE_URL="", POSTGRES_PASSWORD="secret").DATABASES["default"]
        self.assertEqual(
            (database["NAME"], database["USER"], database["PASSWORD"], database["HOST"], database["PORT"]),
            ("campus_ride", "postgres", "secret", "127.0.0.1", "5432"),
        )

    def test_redis_cache_per_release(self):
        settings = self.reload(REDIS_URL="redis://cache:6379/0", DEBUG="")
        self.assertEqual(settings.CACHES["default"]["BACKEND"], "django.core.cache.backends.redis.RedisCache")
        self.assertEqual(settings.CACHES["templates"]["KEY_PREFIX"], f"templates-{settings.STATIC_VERSION}")

    def test_site_url_is_allowed_and_trusted(self):
        settings = self.reload(SITE_URL="https://test.kyyti.net/")
        self.assertIn("test.kyyti.net", settings.ALLOWED_HOSTS)
        self.assertIn("https://test.kyyti.net", settings.CSRF_TRUSTED_ORIGINS)
        self.assertIn("https://test.kyyti.net", settings.CORS_ALLOWED_ORIGINS)
