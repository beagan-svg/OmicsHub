from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Re-key UserPreferences from per-session to per-user.

    The old table stored one row per browser session (ephemeral), so it is
    dropped and recreated keyed by the user.
    """

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ocs', '0010_queuecontrol_timer'),
    ]

    operations = [
        migrations.DeleteModel(name='UserPreferences'),
        migrations.CreateModel(
            name='UserPreferences',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, related_name='preferences', to=settings.AUTH_USER_MODEL)),
                ('column_settings', models.JSONField(default=dict)),
                ('filter_preferences', models.JSONField(default=dict)),
                ('theme', models.CharField(choices=[('light', 'Light'), ('dark', 'Dark'), ('auto', 'Auto')], default='light', max_length=10)),
                ('default_page_size', models.IntegerField(choices=[(10, '10 per page'), (25, '25 per page'), (50, '50 per page'), (100, '100 per page')], default=25)),
                ('auto_refresh_enabled', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'user_preferences',
            },
        ),
    ]
