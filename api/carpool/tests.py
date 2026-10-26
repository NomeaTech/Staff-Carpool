import importlib
import json
import os
from unittest.mock import patch

import requests
from django.core.cache import cache
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

import carpool.settings as project_settings
from accounts.models import User

DSN = "https://publickey@o1.ingest.de.sentry.io/42"


def envelope(dsn=DSN):
    return "\n".join([json.dumps({"event_id": "a" * 32, "dsn": dsn}), json.dumps({"type": "event"}), "{}"]).encode()


@override_settings(SENTRY_DSN=DSN)
class TunnelTests(TestCase):
    """The browser's errors and bug reports, passed on to Sentry (carpool/sentry.py tunnel)."""

    def post(self, body):
        return self.client.post("/app/support/relay/", body, content_type="text/plain;charset=UTF-8")

    def test_passes_our_envelopes_on_to_sentry(self):
        with patch("carpool.sentry.requests.post") as post:
            post.return_value.status_code = 200
            response = self.post(envelope())
        self.assertEqual(response.status_code, 200)
        url = post.call_args.args[0]
        self.assertEqual(url, "https://o1.ingest.de.sentry.io/api/42/envelope/")
        self.assertEqual(post.call_args.kwargs["data"], envelope())

    def test_the_same_dsn_spelled_differently(self):
        with patch("carpool.sentry.requests.post") as post:
            post.return_value.status_code = 200
            self.assertEqual(self.post(envelope(DSN + "/")).status_code, 200)

    def test_refuses_other_projects(self):
        with patch("carpool.sentry.requests.post") as post:
            for dsn in ("https://publickey@o1.ingest.de.sentry.io/43", "https://otherkey@o1.ingest.de.sentry.io/42",
                        "https://publickey@evil.example/42", None):
                self.assertEqual(self.post(envelope(dsn)).status_code, 400, dsn)
            self.assertEqual(self.post(b"not json\n{}").status_code, 400)
        post.assert_not_called()

    def test_sentry_unreachable(self):
        with patch("carpool.sentry.requests.post", side_effect=requests.ConnectionError), \
                self.assertLogs("carpool.sentry", "WARNING"):
            self.assertEqual(self.post(envelope()).status_code, 502)

    def test_only_posts(self):
        self.assertEqual(self.client.get("/app/support/relay/").status_code, 405)

    @override_settings(SENTRY_DSN="")
    def test_off_without_sentry(self):
        self.assertEqual(self.post(envelope()).status_code, 404)

    def test_pages_send_through_it(self):
        response = self.client.get("/app/accounts/login/")
        self.assertContains(response, '"tunnel": "/app/support/relay/"')
        self.assertContains(response, "js/vendor/kyyti-support-")
        # Ad blockers block scripts named after Sentry
        self.assertNotRegex(response.content.decode(), r"<script[^>]+src=\"[^\"]*sentry")


@override_settings(SENTRY_DSN=DSN, SENTRY_RELEASE="lut-kyyti@1.2.3", SENTRY_ENVIRONMENT="testing")
class BugReportFormTests(TestCase):
    """The app's own "Report a bug" form, where Sentry's is blocked (home/views.py report_bug)."""

    def setUp(self):
        # The hourly limit is counted in the cache, which tests share
        cache.clear()
        self.user = User.objects.create_user("aino", email="aino@lut.fi", password="Secret-12345",
                                             email_confirmed_at=timezone.now())
        self.client.force_login(self.user)

    def send(self, message="The map does not load", **headers):
        return self.client.post("/app/support/report/", {"message": message, "page": "http://testserver/app/search/"},
                                headers={"user-agent": "Firefox/140", **headers})

    def test_more_page_links_to_it(self):
        # The link works without the script; the script opens Sentry's form instead
        self.assertContains(self.client.get("/app/more/"), 'href="/app/support/report/" data-bug-report')

    def test_sends_it_to_sentry_as_feedback(self):
        with patch("carpool.sentry.requests.post") as post:
            post.return_value.status_code = 200
            response = self.send()
        self.assertRedirects(response, "/app/more/")
        header, item, feedback = (json.loads(line) for line in post.call_args.kwargs["data"].split(b"\n"))
        self.assertEqual(header["dsn"], DSN)
        self.assertEqual(item, {"type": "feedback"})
        self.assertEqual(feedback["type"], "feedback")
        self.assertEqual(feedback["contexts"]["feedback"], {"message": "The map does not load",
                                                            "url": "http://testserver/app/search/"})
        self.assertEqual(feedback["user"], {"id": str(self.user.pk)})
        self.assertEqual((feedback["release"], feedback["environment"]), ("lut-kyyti@1.2.3", "testing"))
        self.assertEqual(feedback["request"]["headers"]["User-Agent"], "Firefox/140")
        # Nothing else about the member
        self.assertNotIn("aino", json.dumps(feedback))

    def test_needs_a_description(self):
        with patch("carpool.sentry.requests.post") as post:
            response = self.send("   ")
        self.assertContains(response, "Describe the problem before sending the report.")
        post.assert_not_called()

    def test_keeps_the_text_when_sending_fails(self):
        with patch("carpool.sentry.requests.post") as post:
            post.return_value.status_code = 500
            response = self.send()
        self.assertContains(response, "The report could not be sent.")
        self.assertContains(response, "The map does not load")

    def test_limited_per_hour(self):
        with patch("carpool.sentry.requests.post") as post:
            post.return_value.status_code = 200
            for _ in range(10):
                self.send()
            response = self.send()
        self.assertContains(response, "You have sent many reports in a short time.")
        self.assertEqual(post.call_count, 10)

    def test_page_from_another_site_is_not_sent(self):
        response = self.client.get("/app/support/report/", headers={"referer": "https://evil.example/"})
        self.assertContains(response, 'name="page" value="http://testserver/app/more/"')

    def test_needs_login(self):
        self.client.logout()
        self.assertRedirects(self.client.get("/app/support/report/"), "/app/accounts/login?next=/app/support/report/",
                             fetch_redirect_response=False)

    @override_settings(SENTRY_DSN="")
    def test_off_without_sentry(self):
        self.assertEqual(self.client.get("/app/support/report/").status_code, 404)


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
