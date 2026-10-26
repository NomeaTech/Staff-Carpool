# Deployment

The app runs on an Ubuntu Server with [Coolify](https://coolify.io), an open
source platform installed on the server itself. Its dashboard is where
releases are deployed, rolled back and watched: the logs, the settings
(environment variables), the scheduled jobs and the backups.

```
            internet
               │  HTTPS (certificates from Let's Encrypt)
         ┌─────▼─────┐
         │  Traefik  │  Coolify's proxy: sends each address to its app
         └─────┬─────┘
     ┌─────────┴───────────┐
┌────▼──────┐        ┌─────▼─────┐
│ production│        │  staging  │   the app's image (Dockerfile), with Gunicorn
│  (main)   │        │ (testing) │
└──┬─────┬──┘        └──┬─────┬──┘
   │     │              │     │
PostGIS Redis       PostGIS Redis    each environment has its own
```

## How a deploy works

1. A push to `testing` (staging) or `main` (production) starts a deploy, or
   press **Deploy** in the dashboard.
2. Coolify builds a new image on the server (`Dockerfile`): the stylesheet,
   the translations and the static files are all built in it. This takes a
   few minutes, and the running release keeps serving meanwhile.
3. It starts the new release beside the old one. The new one migrates the
   database (`docker/entrypoint`) and starts Gunicorn.
4. Once the new release answers its health check (`/healthz`: it can reach
   the database and Redis), the traffic moves to it. The old one finishes the
   requests it has, then stops.

If the build, a migration or the health check fails, the old release keeps
serving and nothing changes for the members. Coolify can notify you of it.

### Migrations

For a moment, the old release serves with the migrated database, so a
migration must not break the release before it:

- Adding a table, or a column that may be empty or has a default: fine.
- Removing or renaming a column or table: in two releases. First stop using
  it in the code; remove it in a later release.
- Making a column required: first fill it in and write it everywhere, then
  make it required in a later release.

## What you need

- A server with Ubuntu Server 24.04 LTS (or 22.04/26.04): 2 or more CPUs and
  4 GB of memory, 8 GB with Metabase. 40 GB of disk or more. A provider in
  the EU, as the data is members' personal data.
- Your SSH key on it (`ssh-copy-id <you>@<server>`), and a user with `sudo`.
- DNS records (A, and AAAA if the server has IPv6) pointing to the server:
  - `kyyti.net`: production
  - `test.kyyti.net`: staging (or another name)
  - `deploy.kyyti.net`: Coolify's dashboard (or another name)
  - `stats.kyyti.net`: Metabase, if it is hosted
- An admin of the NomeaTech GitHub organisation, to connect the repository.
- S3-compatible storage for off-site backups (e.g. Hetzner, UpCloud or
  Scaleway Object Storage, in the EU).

## 1. Set up the server

From the repository on your computer:

```
scp scripts/server-setup <you>@<server>:
ssh -t <you>@<server> sudo bash server-setup
```

It asks for an email and password for Coolify's admin account, then installs
updates, swap, the firewall and SSH settings, the folders for uploaded files
with their daily backup, and Coolify (see the top of `scripts/server-setup`).
It takes about 5–10 minutes. Before logging out, check in another terminal
that you can still log in over SSH.

Open the dashboard at `http://<server>:8000` and log in **right away**.

## 2. In Coolify

### The dashboard's own address

1. Settings › Instance's Domain: `https://deploy.kyyti.net`. Save, and wait a
   minute for its certificate.
2. Open `https://deploy.kyyti.net` and log in there.
3. Close the ports the dashboard was first reached on:
   ```
   ssh -t <you>@<server> sudo bash server-setup lock-dashboard https://deploy.kyyti.net
   ```
4. Your profile › Two-factor authentication: turn it on.

### Connect GitHub

Sources › Add › GitHub App, and register it to the **NomeaTech** organisation
with access to the Staff-Carpool repository only. Pushes then start deploys.

### Notifications

Settings › Notifications: email, Slack, Discord or Telegram. Turn on at least
failed deployments, failed backups and scheduled task failures.

### Backups

Storages (S3) › Add: your S3 storage's endpoint, bucket and keys.

### The project

Projects › Add: `LUT Kyyti`. It starts with the environment `production`;
add another: `staging`. Do the following in **each** environment.

#### a. The database

1. \+ New › Databases › PostgreSQL. When asked which, choose **PostGIS**.
   Use the same major version as the current server's PostgreSQL, or newer.
2. Initial database: `campus_ride`. Start it.
3. Copy its **Postgres URL (internal)**, for `DATABASE_URL` below.
4. Backups › Add scheduled backup: frequency `0 3 * * *`, keep 14, and
   turn on S3 with the storage above.

#### b. Redis

\+ New › Databases › Redis. Start it, and copy its **Redis URL (internal)**,
for `REDIS_URL` below.

#### c. The app

\+ New › Private Repository (with GitHub App) › Staff-Carpool:

- Branch: `main` in production, `testing` in staging.
- Build Pack: **Dockerfile** (`/Dockerfile`, base directory `/`).
- Ports Exposes: `8000`. Leave Ports Mappings empty: with it, Coolify cannot
  switch releases without downtime.
- Domains: `https://kyyti.net` in production, `https://test.kyyti.net` in staging.

**Environment Variables** (Developer view lets you paste them all at once).
Copy the values from the current server's `api/.env` where it says so:

| Variable | Value |
| --- | --- |
| `SECRET_KEY` | Production: the current server's (otherwise everyone is logged out and reset links stop working). Staging: a new one: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DATABASE_URL` | The database's internal URL (a) |
| `REDIS_URL` | Redis's internal URL (b) |
| `SITE_URL` | `https://kyyti.net`, or `https://test.kyyti.net` |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | Production: the current server's (otherwise members' push notifications stop). Staging: new ones, `python manage.py generate_vapid_keys` |
| `TURNSTILE_SECRET` | The current server's |
| `GOOGLE_MAPS_API_KEY`, `GOOGLE_MAPS_SERVER_KEY` | The current server's |
| `DIGITRANS_SUBSCRIPTION_KEY` | The current server's |
| `RESEND_API_KEY` | The current server's (without it, no emails are sent) |
| `SENTRY_DSN` | Sentry's DSN (README.md, "Sentry") |
| `SENTRY_ENVIRONMENT` | `production`, or `testing` |
| `METABASE_URL` | Optional: `https://stats.kyyti.net` |
| `WEB_CONCURRENCY` | Optional: Gunicorn's processes, 3 if unset (about 150 MB each) |

Leave `DEBUG`, `STATIC_ROOT` and `POSTGRES_PASSWORD` unset: the image sets
what it needs. Leave `CSRF_COOKIE_DOMAIN` unset too: set to `kyyti.net` in
production, its cookie would also reach `test.kyyti.net`, and the two sites
would overwrite each other's, so that forms fail on staging.

For staging, also add `test.kyyti.net` to the hostnames of the Turnstile
widget in Cloudflare, and to the allowed websites of the Google Maps key.

**Persistent Storage** › Add › Directory Mount:

- Source: `/srv/kyyti/production/private_media` (or `.../staging/...`)
- Destination: `/app/api/private_media`

**Healthcheck**: turn it on, with path `/healthz`, port `8000`, and start
period `120` seconds (the first start migrates the database). This is what
lets Coolify switch releases without downtime.

**Scheduled Tasks**: add the jobs in [CRONJOBS.md](CRONJOBS.md).

Deploy. The first deploy takes longest. Then, in the app's Terminal:

```
python manage.py createsuperuser
```

(Not needed if you moved the data from the current server, below.)

## Releasing

- **Staging:** `git ship` (scripts/git-ship) pushes `testing`, and staging
  deploys by itself.
- **Production:** once staging is fine, bring `main` up to `testing`
  (a pull request from `testing` to `main`, or `git push origin testing:main`).
  Production deploys by itself. To deploy production only by pressing Deploy
  in the dashboard instead, turn off its Auto Deploy (the app's Advanced settings).
- **Rolling back:** the app's Rollback lists the earlier images; one click
  switches back, the same way as a deploy. Migrations are not undone, which is
  one more reason for the rule in "Migrations".
- **Logs:** the app's Logs (errors come with their traceback), and each
  deploy's log in Deployments.

## Moving from the current server

Pick a quiet time, and tell the members of a short break.

1. Lower the TTL of the DNS records to 5 minutes a day before.
2. Set up the new server (1 and 2 above), with production's database and
   app, but do not deploy yet.
3. On the **current** server, stop the app and save the data:
   ```
   sudo systemctl stop django_ride
   sudo -u postgres pg_dump -Fc campus_ride > campus_ride.dump
   tar -czf private_media.tar.gz -C <repository>/api private_media
   ```
4. Copy both to the new server (`scp`), and there:
   ```
   # The database's container: the name next to the postgis image
   sudo docker ps --format '{{.Names}}  {{.Image}}' | grep postgis
   sudo docker exec -i <container> pg_restore -U postgres -d campus_ride --no-owner --no-privileges < campus_ride.dump
   sudo tar -xzf private_media.tar.gz -C /srv/kyyti/production
   sudo chown -R 10001:10001 /srv/kyyti/production/private_media
   ```
5. Deploy production in Coolify, and point the `kyyti.net` DNS record to the
   new server. Coolify gets its certificate once the record reaches it.
6. Check that you can log in, see your rides, and get a push notification.
7. Afterwards: remove `.github/workflows/deploy.yml` (it still deploys to the
   current server), and shut the current server down once you are sure.

## Metabase

\+ New › Service › Metabase, in production, with the domain
`https://stats.kyyti.net`. It comes with its own database for its settings;
add a backup to it as for the app's. In its settings, turn on "Connect To
Predefined Network", so that it can reach the app's database.

Then create the read-only user Metabase asks questions as, in the app's database:

```
sudo docker exec -i <postgis container> psql -U postgres -d campus_ride \
  -v reader_password='…' -v app_password='…' < scripts/metabase/setup-database.sql
```

(`app_password` is for a database Metabase does not use in Coolify.) In
Metabase, add the database with the host being the database's container name,
port `5432`, database `campus_ride` and user `metabase_reader`, and carry on
from step 8 of `scripts/metabase/README.md`.

## Trying the image on your own machine

With Docker installed: `docker compose up --build`, then open
http://localhost:8000. See the top of `compose.yaml`.

## When something goes wrong

- **A deploy failed:** its log is in the app's Deployments. The old release is
  still serving.
- **The app shows errors:** the app's Logs, and Sentry.
- **A shell in the app:** the app's Terminal (e.g. `python manage.py shell`).
- **The dashboard cannot be reached at its address:** through an SSH tunnel,
  `ssh -L 8000:localhost:8000 <you>@<server>`, then http://localhost:8000; or
  open its ports again with `sudo bash server-setup unlock-dashboard`.
