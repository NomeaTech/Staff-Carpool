"""
/healthz: whether this copy of the app can serve pages. A deploy only moves
the traffic to the new release once it answers "ok" (DEPLOYMENT.md), so a
release that cannot reach the database or the cache never replaces the one
that works.
"""
import logging

from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.views.decorators.cache import never_cache

logger = logging.getLogger(__name__)


@never_cache
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        # Sessions and the login throttle are in the cache (Redis on the server)
        cache.get("healthz")
    except Exception:
        logger.exception("Health check failed")
        return HttpResponse("unavailable", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
