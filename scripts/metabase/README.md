# Metabase

Metabase answers questions about how the app is used, on top of read-only
views in the `analytics` schema (migration `accounts/0023_analytics_views`).
The views leave out names, email addresses, phone numbers, messages, the test
user and the test rides. `analytics.events` is the activity log
(`api/activity/models.py` lists each kind of event and its `data`). Metabase runs in Docker on the app's server, with
its own database for its settings, behind nginx.

On a server with Coolify, set it up as in `DEPLOYMENT.md` ("Metabase")
instead: Coolify runs it and its database, and serves it over HTTPS, so only
`setup-database.sql` and step 8 below are needed. The steps below are for a
server without Coolify, with PostgreSQL installed on the server itself.

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
8. In Admin → Table Metadata → analytics, click each column below and set its
   semantic type (for a foreign key, also its target):

   | Column | Semantic type |
   | --- | --- |
   | `events.user_id`, `notifications.recipient_id`, `push_subscriptions.user_id`, `ride_requests.passenger_id`, `rides.driver_id` | Foreign Key → Users → ID |
   | `events.ride_id`, `notifications.ride_id`, `ride_requests.ride_id` | Foreign Key → Rides → ID |
   | `rides.start_lat`, `rides.destination_lat` | Latitude |
   | `rides.start_lng`, `rides.destination_lng` | Longitude |

   Or with an API key (Admin → Settings → Authentication → API keys, group
   Administrators): `PUT /api/field/<id>` with
   `{"semantic_type": "type/FK", "fk_target_field_id": <users.id's field id>}`,
   `{"semantic_type": "type/Latitude"}` or `{"semantic_type": "type/Longitude"}`.
   `GET /api/table/<id>/query_metadata` lists a table's field ids. Delete the
   key afterwards.
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
