from django.db import migrations


class Migration(migrations.Migration):
    """The address was never used. Removed before its Address model (test_app 0044)."""

    dependencies = [
        ('accounts', '0020_email_notifications'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='address',
        ),
    ]
