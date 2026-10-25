# Metabase

Metabase answers questions about how the app is used, on top of read-only
views in the `analytics` schema (migration `accounts/0023_analytics_views`).
The views leave out names, email addresses, phone numbers, messages, the test
user and the test rides. `analytics.events` is the activity log
(`api/activity/models.py` lists each kind of event and its `data`). Metabase runs in Docker on the app's server, with
its own database for its settings, behind nginx.

## Setting it up (once, on the server)

1. Deploy, so that the analytics views exist (`python manage.py migrate`).
2. Create the database users, with two new long random passwords:
   ```
   sudo -u postgres psql -d campus_ride -v reader_password='…' -v app_password='…' -f scripts/metabase/setup-database.sql
   ```
3. Install Docker if needed: `curl -fsSL https://get.docker.com | sudo sh`
4. Settings: `sudo install -m 600 scripts/metabase/metabase.env.example /etc/metabase.env`,
   then put the `app_password` and the address in `/etc/metabase.env`.
5. Start it: `sudo scripts/metabase/run`
6. HTTPS: follow the steps at the top of `nginx.conf`.
7. Open the address, create the admin account and add the database:
   PostgreSQL, host `127.0.0.1`, port `5432`, database `campus_ride`, user
   `metabase_reader` with the `reader_password`, schemas "Only these…": `analytics`.
8. In Admin → Table Metadata → analytics, set the `*_id` columns as foreign
   keys to `users.id` / `rides.id`, and `*_lat` / `*_lng` as latitude and longitude.
9. Link it from the admin's user statistics: `METABASE_URL=https://…` in `api/.env`,
   then `sudo systemctl restart django_ride`.
10. Daily backups of Metabase's own database: add the line at the top of `backup` to `sudo crontab -e`.

## Updating

`sudo scripts/metabase/backup`, change `VERSION` in `run`
(https://github.com/metabase/metabase/releases), then `sudo scripts/metabase/run`.

## When the views change

Change them in a new migration (`CREATE OR REPLACE VIEW`). New views are
readable by Metabase without granting again. In Metabase, Admin → Databases →
Sync database schema now shows the new columns.
