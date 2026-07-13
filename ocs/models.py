from django.db import models
from django.utils import timezone

class Metadata(models.Model):
    fastq_name = models.CharField(max_length=255, primary_key=True)
    organism_name = models.CharField(max_length=255, null=True, blank=True)
    library_prep_method_name = models.CharField(max_length=255, null=True, blank=True)
    studies = models.CharField(max_length=255, null=True, blank=True)
    alignment_method = models.CharField(max_length=255, null=True, blank=True)
    amplification_id = models.BigIntegerField(null=True, blank=True)
    amplification_name = models.CharField(max_length=255, null=True, blank=True)
    batch_name_from_vendor = models.CharField(max_length=255, null=True, blank=True)
    cell_capture = models.IntegerField(null=True, blank=True)
    cell_prep_type = models.CharField(max_length=255, null=True, blank=True)
    library_prep_method_id = models.BigIntegerField(null=True, blank=True)
    library_prep_name = models.CharField(max_length=255, null=True, blank=True)
    organism_common_name = models.CharField(max_length=255, null=True, blank=True)
    sample_id = models.BigIntegerField(null=True, blank=True)
    sample_name = models.CharField(max_length=255, null=True, blank=True)
    sample_type = models.CharField(max_length=255, null=True, blank=True)
    sequencing_vendor = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'metadata'

    def __str__(self):
        return self.fastq_name

class Alignment(models.Model):
    fastq_name = models.OneToOneField(Metadata, on_delete=models.CASCADE, primary_key=True)
    status_id = models.CharField(max_length=255)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    fid = models.CharField(max_length=255, null=True, blank=True)
    demand_id = models.CharField(max_length=255, null=True, blank=True)
    retry_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'alignment'

    def __str__(self):
        return f"{self.fastq_name} - {self.status_id}"

class PostQC(models.Model):
    fastq_name = models.OneToOneField(Metadata, on_delete=models.CASCADE, primary_key=True)
    status_id = models.CharField(max_length=255)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    fid = models.CharField(max_length=255, null=True, blank=True)
    demand_id = models.CharField(max_length=255, null=True, blank=True)
    retry_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'postqc'

    def __str__(self):
        return f"{self.fastq_name} - {self.status_id}"

class Ingest(models.Model):
    fastq_name = models.OneToOneField(Metadata, on_delete=models.CASCADE, primary_key=True)
    status_id = models.CharField(max_length=255)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    fid = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'ingest'

    def __str__(self):
        return f"{self.fastq_name} - {self.status_id}"

class LoadAssociation(models.Model):
    fastq_name = models.ForeignKey(Metadata, on_delete=models.CASCADE)
    load_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'load_association'

    def __str__(self):
        return f"{self.fastq_name} - {self.load_name}"

class Main(models.Model):
    fastq_name = models.OneToOneField(Metadata, on_delete=models.CASCADE, primary_key=True, related_name='main')
    study_set = models.CharField(max_length=255, null=True, blank=True)
    library_prep_method = models.CharField(max_length=255, null=True, blank=True)
    organism = models.CharField(max_length=255, null=True, blank=True)
    alignment_status = models.CharField(max_length=50, null=True, blank=True)
    postqc_status = models.CharField(max_length=50, null=True, blank=True)
    ingest_status = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'main'
        managed = False  # Prevent Django from trying to create/modify this table
        ordering = ['fastq_name']  # Add default ordering to prevent UnorderedObjectListWarning

    def __str__(self):
        return str(self.fastq_name)

class UserPreferences(models.Model):
    """One row per user. Settings follow the user across devices."""
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='preferences',
    )

    # Samples-page view state, synced across devices.
    column_settings = models.JSONField(default=dict)
    filter_preferences = models.JSONField(default=dict)

    # Profile-page settings.
    theme = models.CharField(max_length=10, default='light', choices=[
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto'),
    ])
    default_page_size = models.IntegerField(default=25, choices=[
        (10, '10 per page'),
        (25, '25 per page'),
        (50, '50 per page'),
        (100, '100 per page'),
    ])
    auto_refresh_enabled = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_preferences'

class QueueJobs(models.Model):
    fastq_name = models.CharField(max_length=255, primary_key=True)
    alignment_command = models.TextField(null=True, blank=True)
    postqc_command = models.TextField(null=True, blank=True)
    time = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default='Ready')
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='queue_jobs',
        help_text="The user who queued this job. Null means no owner (superuser-only)."
    )

    class Meta:
        db_table = 'queue_jobs'
        ordering = ['-time']

    def __str__(self):
        return self.fastq_name


class QueueControl(models.Model):
    """Singleton holding the global state of the shared queue processor.

    Only superusers change this. The backend ``process_queue`` command submits
    jobs only while ``state == 'running'``.
    """
    STATE_RUNNING = 'running'
    STATE_PAUSED = 'paused'
    STATE_STOPPED = 'stopped'
    STATE_CHOICES = [
        (STATE_RUNNING, 'Running'),
        (STATE_PAUSED, 'Paused'),
        (STATE_STOPPED, 'Stopped'),
    ]

    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=STATE_RUNNING)
    interval_minutes = models.PositiveIntegerField(
        default=3,
        help_text="Auto-submit interval: the backend submits one job each time this many minutes elapse."
    )
    last_processed_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the backend last submitted a job (the global-timer anchor)."
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta:
        db_table = 'queue_control'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Queue: {self.state}"

class RunningJob(models.Model):
    fastq_name = models.CharField(max_length=255, primary_key=True)
    alignment_command = models.TextField(null=True, blank=True)
    postqc_command = models.TextField(null=True, blank=True)
    time = models.DateTimeField(auto_now_add=True)
    alignment_attempts = models.IntegerField(default=0)
    postqc_attempts = models.IntegerField(default=0)
    alignment_demand_id = models.CharField(max_length=255, null=True, blank=True)
    postqc_demand_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'running_jobs'

class FailedJob(models.Model):
    fastq_name = models.CharField(max_length=255, primary_key=True)
    alignment_command = models.TextField(null=True, blank=True)
    postqc_command = models.TextField(null=True, blank=True)
    time = models.DateTimeField(auto_now_add=True)
    alignment_attempts = models.IntegerField(default=0)
    postqc_attempts = models.IntegerField(default=0)
    alignment_demand_id = models.CharField(max_length=255, null=True, blank=True)
    postqc_demand_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'failed_jobs'

class CompletedJob(models.Model):
    STATUS_CHOICES = [
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
        ('Cancelled', 'Cancelled')
    ]

    fastq_name = models.CharField(max_length=255, primary_key=True)
    alignment_command = models.TextField(null=True, blank=True)
    postqc_command = models.TextField(null=True, blank=True)
    alignment_attempts = models.IntegerField(default=0)
    postqc_attempts = models.IntegerField(default=0)
    alignment_demand_id = models.CharField(max_length=255, null=True, blank=True)
    postqc_demand_id = models.CharField(max_length=255, null=True, blank=True)
    alignment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, null=True, blank=True)
    postqc_status = models.CharField(max_length=20, choices=STATUS_CHOICES, null=True, blank=True)
    alignment_start_time = models.DateTimeField(null=True, blank=True)
    alignment_end_time = models.DateTimeField(null=True, blank=True)
    postqc_start_time = models.DateTimeField(null=True, blank=True)
    postqc_end_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'completed_jobs'
