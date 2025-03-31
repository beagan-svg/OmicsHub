from django.db import migrations

def move_start_time_to_end_time(apps, schema_editor):
    """
    Move values from start_time to end_time for Alignment, PostQC, and Ingest models
    """
    # Get the models from the apps registry
    Alignment = apps.get_model('viewer', 'Alignment')
    PostQC = apps.get_model('viewer', 'PostQC')
    Ingest = apps.get_model('viewer', 'Ingest')
    
    # Process Alignment records
    for record in Alignment.objects.filter(start_time__isnull=False):
        # Update all records with non-null start_time
        record.end_time = record.start_time
        record.start_time = None
        record.save(update_fields=['end_time', 'start_time'])
    
    # Process PostQC records
    for record in PostQC.objects.filter(start_time__isnull=False):
        record.end_time = record.start_time
        record.start_time = None
        record.save(update_fields=['end_time', 'start_time'])
    
    # Process Ingest records
    for record in Ingest.objects.filter(start_time__isnull=False):
        record.end_time = record.start_time
        record.start_time = None
        record.save(update_fields=['end_time', 'start_time'])

class Migration(migrations.Migration):
    dependencies = [
        ('viewer', '0002_alter_metadata_studies'),  # Updated to the correct migration
    ]

    operations = [
        migrations.RunPython(move_start_time_to_end_time),
    ] 