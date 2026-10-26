# syntax=docker/dockerfile:1
#
# The app's image, which Coolify builds and runs on the server (DEPLOYMENT.md).
# Everything a release needs is built here: the stylesheet, the translations
# and the static files. A deploy therefore never changes the files of the
# release that is running, and the new one only gets the traffic once its
# health check (/healthz) passes.
#
# To try it on your own machine: docker compose up --build (compose.yaml)

# --- The stylesheet (Tailwind) ---
FROM node:24-slim AS css
WORKDIR /app/api
COPY api/theme/static_src/package.json api/theme/static_src/package-lock.json theme/static_src/
RUN npm ci --prefix theme/static_src
# Tailwind looks for the classes used in the templates and scripts (@source in styles.css)
COPY api/ ./
RUN npm run build --prefix theme/static_src

# --- The app ---
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STATIC_ROOT=/app/staticfiles

# gdal-bin: GDAL, GEOS and PROJ for GeoDjango. libpq5: PostgreSQL's client
# library, for psycopg. gettext: compiles the translations. curl: the health check.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gdal-bin libpq5 gettext curl \
    && rm -rf /var/lib/apt/lists/*

# The app runs as this user. Its uploads folder on the server
# (/srv/kyyti/*/private_media, scripts/server-setup) belongs to the same ID.
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app/api
COPY api/requirements.txt ./
RUN pip install -r requirements.txt

COPY api/ ./
COPY --from=css /app/api/theme/static/css/dist/ theme/static/css/dist/
COPY docker/ /app/docker/

# SECRET_KEY: settings need one to load; the real one is only given when it runs
RUN SECRET_KEY=build-only python manage.py compilemessages --ignore node_modules \
    && SECRET_KEY=build-only python manage.py collectstatic --noinput \
    && mkdir -p private_media \
    && chown app:app private_media

USER app
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

ENTRYPOINT ["/app/docker/entrypoint"]
CMD ["gunicorn", "--config", "/app/docker/gunicorn.conf.py", "carpool.wsgi"]
