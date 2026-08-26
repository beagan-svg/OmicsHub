"""Define the columns shown by the Samples and Data Locations tables."""

from __future__ import annotations

from dataclasses import dataclass

from apps.sample_catalog.models import Stage

# Export demands record inputs but no file store id. Exclude export from this list.
STAGES_WITH_A_FILE_STORE_ID = [stage for stage in Stage if stage != Stage.EXPORT]


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    # text, mono, copy, list, or status
    kind: str = "text"
    # Visibility menu group. Table order follows COLUMNS.
    group: str = "sample"

    def value_for(self, sample, *, raw: bool = False):
        """Return the value for this column on one fastq sample."""
        family, _, stage = self.key.partition(":")
        if family == "status":
            return sample.stage_status(stage)
        if family == "duration":
            return sample.stage_duration_seconds(stage) if raw else sample.stage_duration(stage)
        if family == "demand":
            return sample.stage_demand_id(stage)
        if family == "filestore":
            return sample.stage_file_store_id(stage)

        value = getattr(sample, self.key)
        if self.kind == "list":
            return "+".join(value) if value else ""
        return value


@dataclass(frozen=True)
class ColumnGroup:
    key: str
    label: str
    columns: list[Column]


# The fastq name identifies the row, so the chooser offers it as a locked line rather than
# a checkbox nobody is allowed to clear. Named here so the template does not hard-code it.
LOCKED_COLUMN = "fastq_name"

COLUMNS = [
    Column("fastq_name", "Fastq Name", "mono", "identity"),
    Column("studies", "Study Set", "list", "study"),
    Column("load_name", "Load Name", "mono", "identity"),
    Column("batch_name_from_vendor", "Batch Name From Vendor", group="study"),
    Column("batch_name", "Batch Name", group="study"),
    Column("modality", "Workflow", group="assay"),
    Column("organism_common_name", "Organism Common Name", group="sample"),
    Column("organism_name", "Organism Name", group="sample"),
    Column("library_prep_method_name", "Library Prep Method", group="assay"),
    Column("library_prep_name", "Library Prep Name", group="assay"),
    Column("library_prep_method_id", "Library Prep Method ID", "mono", "assay"),
    Column("sample_names", "Sample Names", "list", "sample"),
    Column("sample_id", "Sample ID", "mono", "sample"),
    Column("sample_type", "Sample Type", group="sample"),
    Column("cell_capture", "Cell Capture", group="sample"),
    Column("cell_prep_type", "Cell Prep Type", group="sample"),
    Column("amplification_name", "Amplification Name", group="assay"),
    Column("amplification_id", "Amplification ID", "mono", "assay"),
    Column("sequencing_vendor", "Sequencing Vendor", group="sequencing"),
    Column("alignment_method", "Alignment Method", group="sequencing"),
    *[Column(f"status:{stage.value}", f"{stage.label}", "status", "status") for stage in Stage],
    # Stage duration columns are hidden by default.
    *[Column(f"duration:{stage.value}", f"{stage.label} Time", group="timing") for stage in Stage],
    # OCS identifiers are copyable values.
    *[Column(f"demand:{stage.value}", f"{stage.label} Demand ID", "copy", "demand") for stage in Stage],
    *[
        Column(f"filestore:{stage.value}", f"{stage.label} File Store ID", "copy", "filestore")
        for stage in STAGES_WITH_A_FILE_STORE_ID
    ],
]

COLUMNS_BY_KEY = {column.key: column for column in COLUMNS}

# Group columns into sections to reduce scanning. Each stage family has its own section.
GROUP_LABELS = [
    ("identity", "Identification"),
    ("study", "Study & batch"),
    ("sample", "Sample"),
    ("assay", "Assay & library prep"),
    ("sequencing", "Sequencing & analysis"),
    ("status", "Pipeline status"),
    ("timing", "Stage timing"),
    ("demand", "Demand IDs"),
    ("filestore", "File store IDs"),
]


# COLUMNS filed into the chooser's sections, each keeping its canonical order.
COLUMN_GROUPS = [
    ColumnGroup(key, label, [column for column in COLUMNS if column.group == key])
    for key, label in GROUP_LABELS
]


# What the old browser showed before anyone touched the column controls.
DEFAULT_COLUMNS = [
    "fastq_name",
    "studies",
    "load_name",
    "batch_name_from_vendor",
    "modality",
    "organism_common_name",
    "library_prep_method_name",
    *[f"status:{stage.value}" for stage in Stage],
]

LOCATION_COLUMNS = [
    Column("load_name", "Load Name", "mono", "sample"),
    Column("batch_name_from_vendor", "Batch Name From Vendor", group="sample"),
    Column("studies", "Study Set", "list", "sample"),
    Column("modality", "Workflow", group="sample"),
    Column("organism_common_name", "Organism Common Name", group="sample"),
    Column("library_prep_method_name", "Library Prep Method", group="sample"),
    Column("stage", "Stage", group="stage"),
    Column("status", "Status", group="stage"),
]
LOCATION_COLUMN_KEYS = {column.key for column in LOCATION_COLUMNS}
LOCATION_DEFAULT_COLUMNS = [column.key for column in LOCATION_COLUMNS]
LOCATION_COLUMN_GROUPS = [
    ColumnGroup("sample", "Sample fields", LOCATION_COLUMNS[:6]),
    ColumnGroup("stage", "Stage fields", LOCATION_COLUMNS[6:]),
]
LOCATION_STAGES = [Stage.INGEST, Stage.ALIGN, Stage.POST_ALIGN]


# Checkout always shows the fields used to build the command.
CHECKOUT_COLUMNS = [
    "fastq_name",
    "studies",
    "load_name",
    "batch_name_from_vendor",
    "modality",
    "organism_common_name",
    "library_prep_method_name",
    *[f"status:{stage.value}" for stage in Stage],
]


def visible_columns(user) -> list[Column]:
    """Return the user's selected columns in canonical order.

    Ordering comes from COLUMNS rather than the stored list so the table reads the same
    for everyone, and an unknown key left over from a removed column is ignored.
    """
    chosen = set(user.visible_columns or DEFAULT_COLUMNS)
    return [column for column in COLUMNS if column.key in chosen]


def visible_location_columns(user) -> list[Column]:
    """Return the selected Data Locations fields, or the defaults."""
    chosen = set(user.visible_location_columns or LOCATION_DEFAULT_COLUMNS)
    return [column for column in LOCATION_COLUMNS if column.key in chosen]


# The fixed set the cart shows, in the canonical order.
CHECKOUT_COLUMN_LIST = [column for column in COLUMNS if column.key in set(CHECKOUT_COLUMNS)]
