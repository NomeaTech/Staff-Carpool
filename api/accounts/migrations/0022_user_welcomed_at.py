from django.db import migrations, models
from django.utils import timezone


def welcome_existing_users(apps, schema_editor):
    # They already use the app, so the welcome popup is only for new accounts
    apps.get_model("accounts", "User").objects.update(welcomed_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0021_remove_user_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='welcomed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(welcome_existing_users, migrations.RunPython.noop),
    ]
