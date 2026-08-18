from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_visible_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="visible_location_columns",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
