import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """The ride model moved to the rides app (rides 0001); its table stays the same."""

    dependencies = [
        ('notifications', '0002_push_subscription'),
        ('rides', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='notification',
                    name='ride',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications', to='rides.ride'),
                ),
            ],
        ),
    ]
