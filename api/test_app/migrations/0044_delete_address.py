from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('test_app', '0043_ride_price'),
        ('accounts', '0021_remove_user_address'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Address',
        ),
    ]
