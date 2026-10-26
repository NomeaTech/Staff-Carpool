# Cron jobs for production

Scheduled jobs for the server. When a feature needs a new scheduled job, add it here.

The app's jobs are **Scheduled Tasks in Coolify** (DEPLOYMENT.md): in the
app's page, Scheduled Tasks › Add, with the name, command and frequency below.
Coolify runs the command in the app's running container, from `api/`, with
the app's environment variables. Its output is in the task's executions.
Set them up in each environment (production and staging).

| Job | When | Needed? | Set up |
| --- | --- | --- | --- |
| Rating reminders | Hourly | Optional, but recommended | Coolify |
| Clear expired sessions | Daily | Recommended | Coolify |
| Database backup | Daily | Yes | Coolify (the database's Backups) |
| Uploaded files backup | Daily | Yes | `scripts/server-setup` does it |
| Metabase backup | Daily | Yes, if Metabase is hosted | Coolify (Metabase's database) |

## Rating reminders

Tells drivers and passengers about trips they can now rate (`api/rides/ratings.py`).
Without this job, the app still sends reminders when anyone opens it for the
first time that day (`api/activity/middleware.py`), but a reminder can then come
hours after the trip. Running it hourly sends them soon after each trip.

- Name: `remind_ratings`
- Command: `python manage.py remind_ratings`
- Frequency: `0 * * * *`

## Clear expired sessions

Sessions are stored in the database (`SESSION_ENGINE = cached_db`), and Django
never deletes expired ones by itself, so the table keeps growing.

- Name: `clearsessions`
- Command: `python manage.py clearsessions`
- Frequency: `30 3 * * *`

## Database backup

In Coolify, the PostgreSQL database's Backups › Add, with frequency `0 3 * * *`.
Turn on uploading to S3 storage, so that a copy is kept off the server
(DEPLOYMENT.md, "Backups").

## Uploaded files backup

The uploaded profile photos (`/srv/kyyti/*/private_media`) are not in the
database. `scripts/server-setup` installs `/usr/local/sbin/kyyti-backup-media`,
which saves a dated copy in `/var/backups/kyyti` at 03:30 every day, keeping the
latest 14 (`/etc/cron.d/kyyti-backup-media`).

## Metabase backup

When Metabase runs in Coolify (DEPLOYMENT.md, "Metabase"), its own database is
part of the Metabase service: add a backup to that database as above.
On a server without Coolify, use `scripts/metabase/backup` instead (see
`scripts/metabase/README.md`).

## Not needed

- Anonymising old activity events: the app does this itself, once a day (`api/activity/middleware.py`).
- `compute_routes`: every deploy runs it (`docker/entrypoint`), for any ride without a route.
- Migrations: every deploy runs them (`docker/entrypoint`).
