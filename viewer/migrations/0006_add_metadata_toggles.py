from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('viewer', '0005_create_userpreferences'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreferences',
            name='show_fastq_name',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_organism_name',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_library_prep_method_name',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_studies',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_alignment_method',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_amplification_id',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_amplification_name',
            field=models.BooleanField(default=True),
        ),
        # show_batch_name already exists
        migrations.AddField(
            model_name='userpreferences',
            name='show_batch_name_from_vendor',
            field=models.BooleanField(default=True),
        ),
        # show_cell_capture already exists
        migrations.AddField(
            model_name='userpreferences',
            name='show_cell_prep_type',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_library_prep_method_id',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_library_prep_name',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_organism_common_name',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_sample_id',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_sample_name',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_sample_type',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userpreferences',
            name='show_sequencing_vendor',
            field=models.BooleanField(default=True),
        ),
    ] 