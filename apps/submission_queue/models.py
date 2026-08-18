from django.conf import settings
from django.db import models

from apps.sample_catalog.models import Sample, Stage


class QueueEntry(models.Model):
    """Store one OCS job requested by a user."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUBMITTING = "SUBMITTING", "Submitting"
        SUBMITTED = "SUBMITTED", "Submitted"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    class ModalitySource(models.TextChoices):
        INFERRED = "inferred", "Inferred from batch name"
        CONFIRMED = "user_confirmed", "Chosen and confirmed by user"

    STAGE_CHOICES = [
        (Stage.ALIGN.value, Stage.ALIGN.label),
        (Stage.POST_ALIGN.value, Stage.POST_ALIGN.label),
    ]

    # PROTECT, not CASCADE: Sample is a mirror that a sync can rebuild, while a submitted
    # entry and its demand id are the only local record that a job was ever sent to OCS.
    # Removing a sample must not take that with it.
    sample = models.ForeignKey(Sample, on_delete=models.PROTECT, related_name="queue_entries")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="queue_entries",
    )

    # No choices: the valid modalities are whatever the uploaded config defines workflows
    # for, so pinning them here would mean a migration every time a modality is added.
    modality = models.CharField(max_length=20)
    modality_source = models.CharField(max_length=20, choices=ModalitySource.choices)
    notify_email = models.EmailField()
    batch_processing = models.BooleanField(default=False)
    forced = models.BooleanField(default=False)

    # The command is built when the entry is queued, so what the user confirmed is
    # exactly what gets run, even if the config is replaced in the meantime.
    command_args = models.JSONField()
    command = models.TextField()
    spacing = models.PositiveIntegerField(help_text="Seconds to wait before the next submission")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    demand_id = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # When the worker took this entry off the queue.
    claimed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            # A sample can only be waiting for one run of a stage at a time. Guards the
            # double-confirm and the concurrent-worker race alike.
            models.UniqueConstraint(
                fields=["sample", "stage"],
                condition=models.Q(status="PENDING"),
                name="one_pending_entry_per_sample_stage",
            ),
        ]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.sample.fastq_name} {self.stage} ({self.status})"


class CartItem(models.Model):
    """Store a fastq sample staged for submission but not yet queued."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    # CASCADE, unlike QueueEntry.sample: a cart item is a staged intention, not a record
    # that a job was sent. If the mirror drops the sample there is nothing to preserve.
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name="cart_items")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "sample"], name="one_cart_item_per_user_sample"),
        ]
        indexes = [models.Index(fields=["user", "added_at"])]

    def __str__(self):
        return f"{self.user} → {self.sample.fastq_name}"
