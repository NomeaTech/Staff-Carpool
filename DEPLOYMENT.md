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
  4 GB of memory (Metabase fits with its memory capped, see "Metabase"; 8 GB
  gives it more room). 40 GB of disk or more. A provider in
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

On violetta the apps are added as a Public Repository instead (the repository
is public), and the GitHub Action `.github/workflows/deploy.yml` starts the
deploys: a push to `testing` deploys staging, one to `main` production, and
the Action fails if the deploy does. It needs one repository secret:

1. In Coolify, Keys & Tokens › API Tokens: a token named `github-actions`,
   with the **deploy** and **read** permissions. Copy it (it is shown once).
2. In GitHub, the repository's Settings › Secrets and variables › Actions ›
   New repository secret: name `COOLIFY_TOKEN`, the token as its value.

If an app is ever made again in Coolify, put its new UUID (in its URL in
Coolify) in `deploy.yml`.

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
what it needs. `SITE_URL` needs the `https://`.

`CSRF_COOKIE_DOMAIN`: production keeps `kyyti.net`, as on the old server.
Members' browsers have that cookie, and without the setting they would send
it beside a new one, so that their forms fail. Leave it unset on staging. The
production cookie also reaches `test.kyyti.net`, so someone who uses both
sites may have to clear staging's cookies if its forms say they expired.

For staging, also add `test.kyyti.net` to the hostnames of the Turnstile
widget in Cloudflare, and to the allowed websites of the Google Maps key.

**Persistent Storage** › Add › Directory Mount:

- Source: `/srv/kyyti/production/private_media` (or `.../staging/...`)
- Destination: `/app/api/private_media`

**Healthcheck**: turn it on, with path `/healthz`, port `8000`, and start
period `120` seconds (the first start migrates the database). This is what
lets Coolify switch releases without downtime.

**Scheduled Tasks**: add the jobs in [CRONJOBS.md](CRONJOBS.md).

Deploy. The first deploy takes longest. Then create the admin account
(see "Running a command in the app" below):

```
kyyti production createsuperuser
```

(Not needed if you moved the data from the current server, below.)

## Running a command in the app

Django's commands (`createsuperuser`, `shell`, `changepassword`, …) run in the
app's container. Coolify names its containers after their IDs, which are random:

| Name starts with | What it is |
| --- | --- |
| `fx0gzv3di7uxvwla74ocpxkz-…` | production's app (kyyti.net) |
| `nfumlq45lf5vteyh6htfbmee-…` | staging's app (test.kyyti.net) |
| `vxldw6odowx1rrscnbnrfgex` | production's database |
| `ufwqtp1aialblxae2vajkqqc` | staging's database |
| `k36idp96tsukciinikiclkzl` | production's Redis |
| `p2ofvcdafwtvhbz7jixr25oc` | staging's Redis |

The part after the app's ID (`-20261026T225845`) is when that release started;
each deploy makes a new one.

**From the command line (easiest):** `scripts/server-setup` installs the
`kyyti` command, which finds the right container itself:

```
ssh violetta
kyyti production createsuperuser     # python manage.py createsuperuser
kyyti staging changepassword <email>  # any manage.py command
kyyti production shell                # Django's shell
kyyti production                      # a plain shell in the container
```

`createsuperuser` asks for a username, an email and a password (twice). Log
in with the email and password, at https://kyyti.net/admin/ for the admin: it
asks you to set up two-step verification the first time.

**From Coolify's dashboard:** Projects › LUT Kyyti › **production** ›
**production-app** › **Terminal**. The list there only shows that app's own
container (`fx0gzv3di7uxvwla74ocpxkz-…`): choose it and press Connect. The
terminal starts in `/app/api`, so type `python manage.py createsuperuser`.
Not the databases' Terminal: they have no Django in them.

## Releasing

- **Staging:** `git ship` (scripts/git-ship) pushes `testing`, and staging
  deploys by itself.
- **Production:** once staging is fine, bring `main` up to `testing`
  (a pull request from `testing` to `main`, or `git push origin testing:main`).
  Production deploys by itself. Each deploy shows in the repository's Actions
  tab, which can also start one again (Deploy with Coolify › Run workflow).
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

\+ New › Service › Metabase, in production. Before deploying:

1. **Edit Compose File**: replace `metabase/metabase:latest` with a version
   (https://github.com/metabase/metabase/releases, e.g. `v0.64.3`), so that a
   redeploy does not upgrade it unasked: an upgrade cannot be undone. Under the
   `metabase` service's `environment:`, add:
   ```
   - JAVA_OPTS=-Xmx768m
   - MB_ANON_TRACKING_ENABLED=false
   ```
   The first keeps its memory to about 1 GB, so that it fits on a 4 GB server
   beside the app; the second stops it sending usage data to Metabase.
2. In the PostgreSQL fields of the General page, **Database Name**: `metabase`
   (Coolify leaves it empty, and will not save the page without it).
3. **Network attachment**: "Connect to the predefined Coolify network", so
   that it can reach the app's database.
4. Domain: `https://stats.kyyti.net` (or `https://stats.kyyti.net:3000`,
   if the page gives 404 or 502: the port is the container's).
5. Its postgresql › Backups: add one as for the app's database.

Deploy, open the address and create Metabase's admin account **right away**:
until then, anyone can.

Then create the read-only user Metabase asks questions as, in the app's database:

```
sudo docker exec -i <postgis container> psql -U postgres -d campus_ride \
  -v reader_password='…' -v app_password='…' < scripts/metabase/setup-database.sql
```

(`app_password` is for a database Metabase does not use in Coolify.) On
violetta, the passwords are in `/root/metabase-passwords`. In Metabase, add the
database: PostgreSQL, the host being the database's container name, port
`5432`, database `campus_ride`, user `metabase_reader`, schemas "Only these…":
`analytics`. Then carry on from step 8 of `scripts/metabase/README.md`.

## Trying the image on your own machine

With Docker installed: `docker compose up --build`, then open
http://localhost:8000. See the top of `compose.yaml`.

## When something goes wrong

- **A deploy failed:** its log is in the app's Deployments. The old release is
  still serving.
- **The app shows errors:** the app's Logs, and Sentry.
- **A shell in the app:** `kyyti production shell` on the server, or the app's Terminal ("Running a command in the app").
- **The dashboard cannot be reached at its address:** through an SSH tunnel,
  `ssh -L 8000:localhost:8000 <you>@<server>`, then http://localhost:8000; or
  open its ports again with `sudo bash server-setup unlock-dashboard`.
