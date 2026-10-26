# Gunicorn's settings in the container (Dockerfile)
import os

bind = "0.0.0.0:8000"

# About 150 MB of memory each. Set WEB_CONCURRENCY in Coolify to change it.
workers = int(os.getenv("WEB_CONCURRENCY", 3))
# Each serves this many requests at once, so that requests that wait for
# another service (errors passed on to Sentry, carpool/sentry.py; Google's
# and Digitransit's APIs) do not hold up the others
worker_class = "gthread"
threads = 4

# A request that takes longer is stopped (e.g. a stuck call to an outside API)
timeout = 60
# When a deploy stops the old release, its workers first finish the requests
# they have, for up to this many seconds
graceful_timeout = 25

# Each worker is replaced after about this many requests, so that slow memory
# leaks never add up
max_requests = 1000
max_requests_jitter = 100

# Requests to stdout, which is the container's log in Coolify. The address is
# the proxy's (Traefik), not the member's.
accesslog = "-"

# The container is only reached through Coolify's proxy, which says whether
# the request came over HTTPS (X-Forwarded-Proto)
forwarded_allow_ips = "*"

# Workers' heartbeat files in memory, not on the container's disk
worker_tmp_dir = "/dev/shm"
