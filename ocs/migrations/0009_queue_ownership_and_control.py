from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def reset_queue(apps, schema_editor):
    """Remove all existing queue rows (they predate ownership) and seed the
    singleton queue-control row in the running state."""
    QueueJobs = apps.get_model('ocs', 'QueueJobs')
    QueueControl = apps.get_model('ocs', 'QueueControl')
    QueueJobs.objects.all().delete()
    QueueControl.objects.update_or_create(pk=1, defaults={'state': 'running'})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ocs', '0008_delete_inprogresssamples_alter_queuejobs_status_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='QueueControl',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(choices=[('running', 'Running'), ('paused', 'Paused'), ('stopped', 'Stopped')], default='running', max_length=10)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'queue_control',
            },
        ),
        migrations.AddField(
            model_name='queuejobs',
            name='user',
            field=models.ForeignKey(blank=True, help_text='The user who queued this job. Null means no owner (superuser-only).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='queue_jobs', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(reset_queue, noop),
    ]
