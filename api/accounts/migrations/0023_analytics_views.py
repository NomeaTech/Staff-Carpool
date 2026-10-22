from django.db import migrations

# Read-only views for Metabase (scripts/metabase), in their own "analytics"
# schema. They leave out personal details (names, email addresses, phone
# numbers, passwords, messages) and, as accounts/stats.py does, the test user
# and the test rides (rides/admin.py TEST_USER_EMAIL and TEST_RIDE_KEY).
# A later migration that drops or changes a column used here fails until the
# view is changed too, so they have to be updated together.
TEST_USER = "test.user@example.com"

VIEWS = rf"""
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE VIEW analytics.users AS
SELECT id, split_part(lower(email), '@', 2) AS domain, date_joined, email_confirmed_at, last_login,
       welcomed_at, is_active, is_staff, (pfp IS NOT NULL AND pfp <> '') AS has_photo,
       (phone IS NOT NULL AND phone <> '') AS has_phone, name_visibility, show_photo, share_email,
       share_phone, email_notifications
FROM accounts_user
WHERE lower(email) <> '{TEST_USER}';

CREATE OR REPLACE VIEW analytics.rides AS
SELECT r.id, r.driver_id, r.created_at, r.offer, r.request, r.train, r.bus, r.taxi, r.other,
       r.one_time, r.one_way, r.max_passengers,
       r.start_json ->> 'displayName' AS start_name, r.destination_json ->> 'displayName' AS destination_name,
       ST_Y(r.start_location::geometry) AS start_lat, ST_X(r.start_location::geometry) AS start_lng,
       ST_Y(r.destination_location::geometry) AS destination_lat, ST_X(r.destination_location::geometry) AS destination_lng,
       -- Stored as text; only well-formed values become timestamps
       CASE WHEN r.leaving_at_date_time ~ '^\d{{4}}-\d{{2}}-\d{{2}}T\d{{2}}:\d{{2}}'
            THEN left(r.leaving_at_date_time, 16)::timestamp END AS leaving_at
FROM rides_ride r
JOIN accounts_user u ON u.id = r.driver_id
WHERE lower(u.email) <> '{TEST_USER}' AND NOT r.start_json @> '{{"test_ride": true}}';

CREATE OR REPLACE VIEW analytics.ride_requests AS
SELECT q.id, q.ride_id, q.passenger_id, q.status, q.created_at, q.updated_at
FROM rides_riderequest q
JOIN analytics.rides r ON r.id = q.ride_id
WHERE q.passenger_id IN (SELECT id FROM analytics.users);

CREATE OR REPLACE VIEW analytics.notifications AS
SELECT n.id, n.recipient_id, n.kind, n.ride_id, n.created_at, n.read_at
FROM notifications_notification n
WHERE n.recipient_id IN (SELECT id FROM analytics.users)
  AND (n.ride_id IS NULL OR n.ride_id IN (SELECT id FROM analytics.rides));

CREATE OR REPLACE VIEW analytics.push_subscriptions AS
SELECT id, user_id, created_at, last_used_at
FROM notifications_pushsubscription
WHERE user_id IN (SELECT id FROM analytics.users);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0022_user_welcomed_at"),
        ("rides", "0001_initial"),
        ("notifications", "0003_alter_notification_ride"),
    ]

    operations = [
        migrations.RunSQL(VIEWS, "DROP SCHEMA IF EXISTS analytics CASCADE;"),
    ]
