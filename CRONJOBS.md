# Cron jobs for production

Scheduled jobs to set up once hosting is finalised. None of them are set up yet.
When a feature needs a new scheduled job, add it here.

The paths below are placeholders: `/srv/Staff-Carpool` for the repository and
`/srv/Staff-Carpool/env` for its virtualenv. Each Django command runs from
`api/`, so that `.env` is found.

| Job | When | Needed? |
| --- | --- | --- |
| Rating reminders | Hourly | Optional, but recommended |
| Clear expired sessions | Daily | Recommended |
| Metabase backup | Daily | Yes, if Metabase is hosted |

## Rating reminders

Tells drivers and passengers about trips they can now rate (`api/rides/ratings.py`).
Without this job, the app still sends reminders when anyone opens it for the
first time that day (`api/activity/middleware.py`), but a reminder can then come
hours after the trip. Running it hourly sends them soon after each trip.

```
0 * * * * cd /srv/Staff-Carpool/api && ../env/bin/python manage.py remind_ratings >> /var/log/kyyti/remind_ratings.log 2>&1
```

## Clear expired sessions

Sessions are stored in the database (`SESSION_ENGINE = cached_db`), and Django
never deletes expired ones by itself, so the table keeps growing.

```
30 3 * * * cd /srv/Staff-Carpool/api && ../env/bin/python manage.py clearsessions
```

## Metabase backup

Saves Metabase's own database (its users, questions and dashboards), keeping
the latest 14. See `scripts/metabase/README.md`. Needs root, so it goes in
`sudo crontab -e`.

```
0 3 * * * /srv/Staff-Carpool/scripts/metabase/backup
```

## Not needed

- Anonymising old activity events: the app does this itself, once a day (`api/activity/middleware.py`).
- `compute_routes`: a one-off, for rides saved before routes were stored.
