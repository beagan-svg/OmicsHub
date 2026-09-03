from django.db import models
from django.db.models import Case, Value, When
from django.utils import timezone


class BatchPrefix(models.TextChoices):
    """Define batch-name-from-vendor families used by dashboard filters."""

    MTX = "MTX", "MTX"
    RFX = "RFX", "RFX"
    ATX = "ATX", "ATX"
    RTX = "RTX", "RTX"


class Modality(models.TextChoices):
    """Define the workflow for a fastq sample. ATX samples run as MTX."""

    MTX = "MTX", "MTX"
    RFX = "RFX", "RFX"
    RTX = "RTX", "RTX"


# The vendor-prefix rule, in one place. The generated columns below are built from this
# mapping rather than repeating it, so the SQL and any Python that needs the same answer
# cannot drift apart. Anything not listed here is RTX.
PREFIX_MODALITY = {
    BatchPrefix.MTX: Modality.MTX,
    # The ATAC half of a multiome experiment. Its own family so it stays selectable, but it
    # runs the MTX workflow. The pair is aligned as one job.
    BatchPrefix.ATX: Modality.MTX,
    BatchPrefix.RFX: Modality.RFX,
}
FALLBACK_PREFIX = BatchPrefix.RTX
FALLBACK_MODALITY = Modality.RTX


def prefixes_for_workflows(workflow_names) -> set[str]:
    """Return batch-name-from-vendor prefixes to sync for manifest workflows.

    Use more than workflow names because ATX has no workflow of its own but must be synced
    whenever MTX is configured, because an MTX submission cannot align without its ATAC
    half. Scoping the sync to workflow names alone is what silently prunes ATX away.
    """
    wanted = {prefix for prefix, mod in PREFIX_MODALITY.items() if mod in workflow_names}
    if FALLBACK_MODALITY in workflow_names:
        wanted.add(FALLBACK_PREFIX)
    return {str(prefix) for prefix in wanted}


# The multiome pair: MTX (GEX) and ATX (ATAC) batches sharing a load_name. Not the
# library prep name -- a vendor's naming for the two halves varies (real synced data has
# used "10xRSeq_Mult"/"10xATAC_Mult" as well as "10xMultX_GEX"/"10xMultX_ATAC") -- and not
# load_name alone either: 262 load_names in the real DynamoDB data are shared by unrelated
# samples, so requiring one MTX and one ATX side is what tells a real pair apart from a
# coincidence.
MULTIOME_PREFIXES = (BatchPrefix.MTX, BatchPrefix.ATX)


class Stage(models.TextChoices):
    """Define OCS stages stored by the sync."""

    INGEST = "ingest", "Ingest"
    ALIGN = "align", "Alignment"
    POST_ALIGN = "post-align", "Post-alignment"
    EXPORT = "export", "Export"


# The status a stage has when OCS has no demand recorded for it at all. The uploaded
# config's status_mappings list the labels that count as complete; anything not in those
# lists, including this one, means the stage still has work to do.
NOT_COMPLETED = "NOT COMPLETED"

# The Sample fields users can filter by, shared by the dashboard's multi-value filter
# panel and the REST API's query parameters so the two cannot silently diverge. The two
# consumers apply it differently on purpose: the web UI accepts several values per field
# (`getlist` + `__in`), the API one exact value per field.
FILTER_FIELDS = ("batch_name_from_vendor", "organism_common_name", "library_prep_method_name")


class Sample(models.Model):
    """Store one OCS fastq metadata entry locally."""

    fastq_name = models.CharField(max_length=255, unique=True)

    batch_name = models.CharField(max_length=255, blank=True)
    batch_name_from_vendor = models.CharField(max_length=255, db_index=True)
    sequencing_vendor = models.CharField(max_length=255, blank=True)

    # Both are derived from the batch-name-from-vendor prefix by the database, not the sync: a
    # generated column cannot drift, so no partial sync, fixture or shell edit can write a
    # sample whose modality disagrees with its batch name.
    #
    # Two fields rather than one because they answer different questions. `batch_prefix` is
    # what the vendor called it, and is what the dashboard's MTX/RTX/ATX toggle filters on.
    # `modality` is which workflow to run, and folds ATX into MTX.
    #
    # They spell out what PREFIX_MODALITY says rather than being generated from it, because
    # altering a GeneratedField means dropping and re-adding a persisted column. The two are
    # pinned together by test_prefix_mapping_matches_the_generated_columns.
    #
    # Everything not listed, including bare 10X* batches, falls through to RTX. There
    # is deliberately no "unknown": a prefix nobody has taught us about is still an RTX
    # sample, not an error state.
    batch_prefix = models.GeneratedField(
        expression=Case(
            When(batch_name_from_vendor__startswith="MTX", then=Value(BatchPrefix.MTX)),
            When(batch_name_from_vendor__startswith="RFX", then=Value(BatchPrefix.RFX)),
            When(batch_name_from_vendor__startswith="ATX", then=Value(BatchPrefix.ATX)),
            default=Value(BatchPrefix.RTX),
        ),
        output_field=models.CharField(max_length=3, choices=BatchPrefix.choices),
        db_persist=True,
    )
    modality = models.GeneratedField(
        expression=Case(
            When(batch_name_from_vendor__startswith="RFX", then=Value(Modality.RFX)),
            # MTX and ATX are the two halves of one multiome experiment and run the same
            # workflow, so they resolve to the same modality.
            When(batch_name_from_vendor__startswith="MTX", then=Value(Modality.MTX)),
            When(batch_name_from_vendor__startswith="ATX", then=Value(Modality.MTX)),
            default=Value(Modality.RTX),
        ),
        output_field=models.CharField(max_length=3, choices=Modality.choices),
        db_persist=True,
    )

    organism_common_name = models.CharField(max_length=255, db_index=True)
    organism_name = models.CharField(max_length=255, blank=True)

    library_prep_method_name = models.CharField(max_length=255, db_index=True)
    library_prep_method_id = models.BigIntegerField(null=True, blank=True)
    library_prep_name = models.CharField(max_length=255, blank=True)

    sample_id = models.BigIntegerField(null=True, blank=True)
    sample_names = models.JSONField(default=list)
    sample_type = models.CharField(max_length=255, blank=True)
    cell_capture = models.IntegerField(null=True, blank=True)
    cell_prep_type = models.CharField(max_length=255, blank=True)

    amplification_id = models.BigIntegerField(null=True, blank=True)
    amplification_name = models.CharField(max_length=255, blank=True)

    load_name = models.CharField(max_length=255, blank=True)
    alignment_method = models.CharField(max_length=255, blank=True)
    studies = models.JSONField(default=list)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fastq_name"]
        indexes = [
            # Backs the dashboard's family toggle, which filters the local data. There is
            # deliberately no matching index on `modality`: nothing filters by it, and the
            # one aggregate that groups by it groups by three columns, which a single-column
            # index cannot serve.
            models.Index(fields=["batch_prefix"]),
            # The multiome partner lookup: find the other batch prefix sharing this load_name.
            models.Index(fields=["load_name", "batch_prefix"]),
        ]

    def __str__(self):
        return self.fastq_name

    @property
    def multiome_partner_prefix(self) -> str | None:
        """Return the batch prefix (MTX or ATX) that would complete this sample's
        multiome pair, or None if this sample's own prefix is neither."""
        if self.batch_prefix == BatchPrefix.MTX:
            return BatchPrefix.ATX
        if self.batch_prefix == BatchPrefix.ATX:
            return BatchPrefix.MTX
        return None

    def stage_record(self, stage: str):
        """Return the synced status for one stage, or None without a record."""
        for record in self.stage_statuses.all():
            if record.stage == stage:
                return record
        return None

    def stage_status(self, stage: str) -> str:
        """Return the raw OCS status, or NOT COMPLETED when no row exists."""
        record = self.stage_record(stage)
        return record.status if record else NOT_COMPLETED

    def stage_duration(self, stage: str) -> str:
        """Return a formatted stage duration, or blank without an OCS duration."""
        record = self.stage_record(stage)
        return record.duration_display if record else ""

    def stage_duration_seconds(self, stage: str):
        """Return the raw stage duration in seconds."""
        record = self.stage_record(stage)
        return record.duration_seconds if record else None

    def stage_demand_id(self, stage: str) -> str:
        """Return the demand id that produced this stage status."""
        record = self.stage_record(stage)
        return record.demand_id if record else ""

    def stage_file_store_id(self, stage: str) -> str:
        """Return the file store id produced by this stage for `ocs gfs` commands."""
        record = self.stage_record(stage)
        return record.file_store_id if record else ""


class StageStatus(models.Model):
    """Store the latest OCS demand for one fastq sample and stage."""

    # CASCADE is right here, unlike on QueueEntry: a stage status is derived from the
    # sample and means nothing without it.
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name="stage_statuses")
    stage = models.CharField(max_length=20, choices=Stage.choices)
    demand_id = models.CharField(max_length=64, blank=True)
    execution_arn = models.CharField(max_length=2048, blank=True)
    # No choices: these are OCS's own status labels, and the config decides which of them
    # count as complete. Enumerating them here would mean a migration whenever OCS adds one.
    status = models.CharField(max_length=32)
    # When OCS last changed the demand, versus when this app last read it. Both matter:
    # the first is the job's age, the second is the page's.
    last_update_time = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    # `duration_seconds` is read from the registry rather than computed from the two
    # timestamps. They disagree: a demand OCS retried carries the elapsed time of the run
    # that counted, while last_update_time − started_at spans every attempt. The registry's
    # number is the one its operators quote.
    #
    # Null is meaningful and distinct from zero: a stage still running has a start and no
    # duration, and a stage OCS has no record of has neither.
    started_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    # What the stage produced, as GFS names it: the sha1 file store id behind a
    # "gfs://…" path. Forty characters exactly, but the column is not fixed-width because
    # blank is the honest value for a demand still running (it has produced nothing yet)
    # and for an ingest row whose outputs cannot be attributed to one sample.
    file_store_id = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["sample", "stage"], name="unique_stage_per_sample"),
        ]
        indexes = [
            # The dashboard filters and the CSV export both select on a stage and a status
            # together. This table runs about four rows per sample, so without this every
            # filtered load sequential-scans it.
            models.Index(fields=["stage", "status"]),
            models.Index(fields=["demand_id"]),
        ]

    def __str__(self):
        return f"{self.sample.fastq_name} {self.stage}: {self.status}"

    @property
    def duration_display(self) -> str:
        """Return the run time in minutes, hours, and days."""
        return self.duration_display_at()

    def duration_display_at(self, at=None) -> str:
        """Return the recorded duration, or the elapsed time for a running stage."""
        seconds = self.duration_seconds
        if seconds is None and self.started_at:
            seconds = max(0, int(((at or timezone.now()) - self.started_at).total_seconds()))
        if seconds is None:
            return ""
        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60
        if days:
            return f"{days}d" + (f" {hours}h" if hours else "") + (f" {minutes}m" if minutes else "")
        if hours:
            return f"{hours}h" + (f" {minutes}m" if minutes else "")
        return f"{minutes}m"
