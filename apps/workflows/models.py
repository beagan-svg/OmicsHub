from django.conf import settings
from django.db import models, transaction


class WorkflowConfig(models.Model):
    """Store an uploaded OCS workflow manifest.

    The config drives every submission decision: which command runs for a given modality,
    library prep and organism, which reference and probe set to use, the job limit, and
    which OCS status labels count as a completed stage. Uploading a new one is how the
pipeline changes without a code edit.

    `raw` keeps the file exactly as uploaded (comments included) so it can be read back
    and diffed; `data` is the parsed, comment-stripped, reference-expanded form that the
    builder reads.
    """

    name = models.CharField(max_length=255)
    raw = models.TextField()
    data = models.JSONField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="workflow_configs",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-uploaded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="only_one_active_workflow_config",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({'active' if self.is_active else 'inactive'})"

    def activate(self):
        """Activate this manifest for new submissions."""
        with transaction.atomic():
            WorkflowConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
            self.is_active = True
            self.save(update_fields=["is_active"])
