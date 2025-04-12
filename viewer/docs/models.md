# OCS Database Models

This document describes the database models used in the OCS Database Viewer application.

## Core Models

### Metadata

The `Metadata` model is the core model that stores basic information about RNA-Seq samples.

| Field | Type | Description |
|-------|------|-------------|
| `fastq_name` | CharField | Primary key, unique identifier for the sample |
| `organism_name` | CharField | Scientific name of the organism |
| `organism_common_name` | CharField | Common name of the organism (e.g., "human", "mouse") |
| `library_prep_method_name` | CharField | Library preparation method (e.g., "10x 3' v3") |
| `studies` | CharField | Study set designation |
| `batch_name` | CharField | Batch name |
| `batch_name_from_vendor` | CharField | Batch name provided by the sequencing vendor |
| `sequencing_vendor` | CharField | Name of the sequencing vendor |
| `amplification_id` | BigIntegerField | ID for the amplification method |
| `amplification_name` | CharField | Name of the amplification method |
| `cell_capture` | IntegerField | Cell capture information |
| `cell_prep_type` | CharField | Cell preparation type |
| `sample_id` | BigIntegerField | Sample ID |
| `sample_name` | CharField | Sample name |
| `sample_type` | CharField | Sample type |

### Main

The `Main` model is a combined view that joins the Metadata model with status information.

| Field | Type | Description |
|-------|------|-------------|
| `fastq_name` | OneToOneField | Foreign key to Metadata |
| `study_set` | CharField | Study set designation |
| `library_prep_method` | CharField | Library preparation method |
| `organism` | CharField | Organism name |
| `alignment_status` | CharField | Current alignment processing status |
| `postqc_status` | CharField | Current post-QC processing status |
| `ingest_status` | CharField | Current ingest processing status |

**Note:** This is a non-managed model (Django doesn't create the database table) because it's a database view.

## Status Models

### Alignment

The `Alignment` model stores information about the alignment processing status for each sample.

| Field | Type | Description |
|-------|------|-------------|
| `fastq_name` | OneToOneField | Foreign key to Metadata |
| `status_id` | CharField | Current status (e.g., "pending", "in_progress", "completed", "failed") |
| `start_time` | DateTimeField | When alignment started |
| `end_time` | DateTimeField | When alignment completed |
| `fid` | CharField | File ID for the alignment output |

### PostQC

The `PostQC` model stores information about the post-alignment quality control processing status.

| Field | Type | Description |
|-------|------|-------------|
| `fastq_name` | OneToOneField | Foreign key to Metadata |
| `status_id` | CharField | Current status |
| `start_time` | DateTimeField | When post-QC started |
| `end_time` | DateTimeField | When post-QC completed |
| `fid` | CharField | File ID for the post-QC output |

### Ingest

The `Ingest` model stores information about the data ingestion processing status.

| Field | Type | Description |
|-------|------|-------------|
| `fastq_name` | OneToOneField | Foreign key to Metadata |
| `status_id` | CharField | Current status |
| `start_time` | DateTimeField | When ingestion started |
| `end_time` | DateTimeField | When ingestion completed |
| `fid` | CharField | File ID for the ingestion output |

## Association Models

### LoadAssociation

The `LoadAssociation` model maps between fastq names and load names.

| Field | Type | Description |
|-------|------|-------------|
| `fastq_name` | ForeignKey | Foreign key to Metadata |
| `load_name` | CharField | Load name |

## User Models

### UserPreferences

The `UserPreferences` model stores user interface preferences.

| Field | Type | Description |
|-------|------|-------------|
| `session_key` | CharField | Primary key, Django session key |
| `show_batch_name` | BooleanField | Whether to show the batch name column |
| `show_cell_capture` | BooleanField | Whether to show the cell capture column |

## Relationships

```
Metadata (fastq_name)
    ├── One-to-One → Main (fastq_name)
    ├── One-to-One → Alignment (fastq_name)
    ├── One-to-One → PostQC (fastq_name)
    ├── One-to-One → Ingest (fastq_name)
    └── One-to-Many → LoadAssociation (fastq_name)
```

## Usage Examples

### Getting a sample's status information

```python
from viewer.models import Metadata

# Get a sample by fastq_name
sample = Metadata.objects.get(fastq_name='SAMPLE1_MX123456')

# Access status information
alignment_status = sample.main.alignment_status
postqc_status = sample.main.postqc_status
ingest_status = sample.main.ingest_status

# Get related records
alignment = sample.alignment
postqc = sample.postqc
ingest = sample.ingest

# Get load associations
load_associations = sample.loadassociation_set.all()
load_names = [la.load_name for la in load_associations]
``` 