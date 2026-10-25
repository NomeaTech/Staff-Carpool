"""
The first step of moving the ride models to the rides app: their tables get
the rides app's names, and so do their content types (so that permissions and
admin history stay with them). rides 0001 then adds the models to the rides
app, and test_app 0046 removes them from this one, without touching the tables.
"""
from django.db import migrations

MODELS = ["ride", "via", "riderequest"]


def move_content_types(apps, schema_editor, from_app="test_app", to_app="rides"):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for model in MODELS:
        if not ContentType.objects.filter(app_label=to_app, model=model).exists():
            ContentType.objects.filter(app_label=from_app, model=model).update(app_label=to_app)


def move_content_types_back(apps, schema_editor):
    move_content_types(apps, schema_editor, from_app="rides", to_app="test_app")


class Migration(migrations.Migration):

    dependencies = [
        ('test_app', '0044_delete_address'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        *(migrations.AlterModelTable(name=model, table=f"rides_{model}") for model in MODELS),
        migrations.RunPython(move_content_types, move_content_types_back),
    ]
