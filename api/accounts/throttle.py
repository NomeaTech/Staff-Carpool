"""
Limits on how often something can be done for an email address, so that
passwords cannot be guessed by trying many, and nobody's inbox can be
flooded with password reset emails.

The counts are kept in the cache (CACHES "default"), by email address and
not by IP address: requests reach the app through a proxy, so the address
they say they come from cannot be trusted.
"""
import hashlib

from django.core.cache import cache

# Wrong passwords for an address before logging in with it waits
LOGIN_ATTEMPTS = 10
LOGIN_WINDOW = 15 * 60
# Password reset emails sent to an address per window
PASSWORD_RESETS = 3
PASSWORD_RESET_WINDOW = 60 * 60


def _key(kind, email):
    # Hashed: cache keys cannot hold every character an address can
    digest = hashlib.sha256((email or "").strip().lower().encode()).hexdigest()
    return f"throttle:{kind}:{digest}"


def blocked(kind, email, limit):
    """Whether email has been counted limit times for kind within its window."""
    return cache.get(_key(kind, email), 0) >= limit


def count(kind, email, window):
    """Counts one more for email; the count is forgotten window seconds after the first."""
    key = _key(kind, email)
    if not cache.add(key, 1, window):
        try:
            cache.incr(key)
        except ValueError:
            # Expired in between
            cache.set(key, 1, window)


def clear(kind, email):
    cache.delete(_key(kind, email))
