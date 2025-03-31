from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('viewer', '0004_merge_20250330_0626'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPreferences',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(max_length=40, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                # Basic columns that were likely already in the model
                ('show_batch_name', models.BooleanField(default=True)),
                ('show_cell_capture', models.BooleanField(default=True)),
            ],
        ),
    ] 