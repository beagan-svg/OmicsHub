from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_user_visible_location_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="queue_paused",
            field=models.BooleanField(default=False),
        ),
    ]
