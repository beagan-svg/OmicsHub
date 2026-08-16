"""Define dashboard columns and their default selection.

The mirror holds all of OCS's fastq-metadata, which is more than fits on a screen, so the
table is column-configurable: this is the single list both the header and the visibility
menu are built from.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.catalog.models import Stage

# A file store id names what a stage *produced*, derived from the output GFS path on its
# fastq-history row. Export has no such column because an export demand records inputs and
# no outputs — 32 inputs, 0 outputs on a real row — so the value is not merely missing, it
# structurally cannot arrive. Its result is registered in DATS instead, which this app does
# not read. An always-empty column in the chooser is a question every reader has to ask
# once, so the honest thing is not to offer it.
STAGES_WITH_A_FILE_STORE_ID = [stage for stage in Stage if stage != Stage.EXPORT]


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    # text | mono (technical identifiers) | copy (identifier, click to copy) |
    # list (joined) | status (badge)
    kind: str = "text"
    # Which section of the visibility menu this column is filed under. Purely a grouping
    # for the chooser — the table itself always renders in COLUMNS order.
    group: str = "sample"

    def value_for(self, sample, *, raw: bool = False):
        """Return this column's value for one fastq sample.

        The per-stage families are keyed `<family>:<stage>` and read through the sample's
        stage accessors; everything else is a field on the sample. `raw` is what the CSV
export wants, a duration as seconds rather than as "2h 48m", because a
        spreadsheet column has to sort and sum and "2h 48m" does neither.
        """
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
    Column("organism_common_name", "Organism", group="sample"),
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
    # How long each stage took, as OCS measured it. Off by default — three more columns on
    # an already-wide table — but the first thing asked for when a run looks slow.
    *[Column(f"duration:{stage.value}", f"{stage.label} Time", group="timing") for stage in Stage],
    # The two identifiers OCS tooling takes: the demand id names the run, the file store id
    # names what the run produced (`ocs gfs list --file-store-id …`). Both exist to be
    # pasted somewhere else, which is why they render as "copy" — a click puts the value on
    # the clipboard rather than making the reader select forty characters by hand.
    *[Column(f"demand:{stage.value}", f"{stage.label} Demand ID", "copy", "demand") for stage in Stage],
    *[
        Column(f"filestore:{stage.value}", f"{stage.label} File Store ID", "copy", "filestore")
        for stage in STAGES_WITH_A_FILE_STORE_ID
    ],
]

COLUMNS_BY_KEY = {column.key: column for column in COLUMNS}

# The order the chooser reads top to bottom. Forty-odd checkboxes in one undifferentiated
# list is a scanning problem: the sections are what let someone looking for "Cell Capture"
# skip four fifths of the menu. The per-stage families get a section each because they
# answer four different questions about the same stage.
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


# The checkout table is deliberately not column-configurable. It answers one question — is
# this the right sample to submit — with the fields the command is built from, and it is not
# the dashboard's choice: columns someone turned on last week to chase a problem should not
# reappear on the page where a mistake costs a run.
CHECKOUT_COLUMNS = [
    "fastq_name",
    "studies",
    "load_name",
    "batch_name_from_vendor",
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


# The fixed set the cart shows, in the canonical order.
CHECKOUT_COLUMN_LIST = [column for column in COLUMNS if column.key in set(CHECKOUT_COLUMNS)]
