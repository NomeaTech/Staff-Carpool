from django.db import migrations


class Migration(migrations.Migration):
    """
    The last step of moving the ride models to the rides app (see 0045): they
    are removed from this app, but their tables are now the rides app's.
    """

    dependencies = [
        ('test_app', '0045_move_models_to_rides'),
        ('rides', '0001_initial'),
        ('notifications', '0003_alter_notification_ride'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='RideRequest'),
                migrations.DeleteModel(name='Via'),
                migrations.DeleteModel(name='Ride'),
            ],
        ),
    ]
