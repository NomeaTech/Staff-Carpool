from django.db import migrations

# The activity log for Metabase (scripts/metabase), next to the views of
# accounts/0023_analytics_views. Events hold no personal details (see
# activity/models.py) and none about the test user or the test rides, which
# are never recorded. user_id is empty for deleted accounts.
VIEW = """
CREATE OR REPLACE VIEW analytics.events AS
SELECT id, user_id, kind, ride_id, data, created_at
FROM activity_event;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("activity", "0001_initial"),
        ("accounts", "0023_analytics_views"),
    ]

    operations = [
        migrations.RunSQL(VIEW, "DROP VIEW IF EXISTS analytics.events;"),
    ]
