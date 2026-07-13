from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ocs', '0009_queue_ownership_and_control'),
    ]

    operations = [
        migrations.AddField(
            model_name='queuecontrol',
            name='interval_minutes',
            field=models.PositiveIntegerField(default=3, help_text='Auto-submit interval: the backend submits one job each time this many minutes elapse.'),
        ),
        migrations.AddField(
            model_name='queuecontrol',
            name='last_processed_at',
            field=models.DateTimeField(blank=True, null=True, help_text='When the backend last submitted a job (the global-timer anchor).'),
        ),
    ]
