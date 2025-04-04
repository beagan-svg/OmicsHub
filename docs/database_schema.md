# Database Schema Documentation

## Overview
This document provides an overview of the database structure for the Database OCS application. The application tracks sample data through various processing stages.

## Database Models

### Metadata
Central table that stores information about each sample (fastq file).

**Table**: `metadata`

**Fields**:
- `fastq_name`: CharField (Primary Key)
- `organism_name`: CharField
- `library_prep_method_name`: CharField
- `studies`: JSONField (Stores a list of study sets)
- `alignment_method`: CharField
- `amplification_id`: BigIntegerField
- `amplification_name`: CharField
- `batch_name`: CharField
- `batch_name_from_vendor`: CharField
- `cell_capture`: IntegerField
- `cell_prep_type`: CharField
- `library_prep_method_id`: BigIntegerField
- `library_prep_name`: CharField
- `organism_common_name`: CharField
- `sample_id`: BigIntegerField
- `sample_name`: CharField
- `sample_type`: CharField
- `sequencing_vendor`: CharField

### Main
Main tracking table with consolidated information about each sample, linked to Metadata.

**Table**: `main`

**Fields**:
- `fastq_name`: OneToOneField (FK -> Metadata, Primary Key)
- `study_set`: CharField
- `organism`: CharField
- `library_prep_method`: CharField
- `alignment_status`: CharField
- `postqc_status`: CharField
- `ingest_status`: CharField

### LoadAssociation
Associates fastq files with load names (many-to-many relationship).

**Table**: `load_association`

**Fields**:
- `id`: BigAutoField (Primary Key)
- `fastq_name`: ForeignKey (FK -> Metadata)
- `load_name`: CharField

**Unique Together**: `(fastq_name, load_name)`

### Alignment
Tracks alignment processing status for each sample.

**Table**: `alignment`

**Fields**:
- `fastq_name`: OneToOneField (FK -> Metadata, Primary Key)
- `status_id`: CharField
- `start_time`: DateTimeField
- `end_time`: DateTimeField
- `fid`: CharField

### PostQC
Tracks post-QC processing status for each sample.

**Table**: `postqc`

**Fields**:
- `fastq_name`: OneToOneField (FK -> Metadata, Primary Key)
- `status_id`: CharField
- `start_time`: DateTimeField
- `end_time`: DateTimeField
- `fid`: CharField

### Ingest
Tracks ingest processing status for each sample.

**Table**: `ingest`

**Fields**:
- `fastq_name`: OneToOneField (FK -> Metadata, Primary Key)
- `status_id`: CharField
- `start_time`: DateTimeField
- `end_time`: DateTimeField
- `fid`: CharField

## Relationships

```
                    ┌───────────────┐
                    │   Metadata    │
                    │ (fastq_name)  │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              │             │             │
┌─────────────▼──┐  ┌───────▼───────┐    │
│ LoadAssociation │  │     Main      │    │
└────────────────┘  └───────────────┘    │
                                          │
                   ┌────────────────┐     │
                   │                │     │
        ┌──────────┤   Processing   ◄─────┘
        │          │                │
        │          └────────┬───────┘
        │                   │
┌───────▼──────┐   ┌────────▼────┐   ┌─────────┐
│  Alignment   │   │   PostQC    │   │  Ingest  │
└──────────────┘   └─────────────┘   └─────────┘
```

## Key Points
1. `Metadata` is the central model with the primary key `fastq_name`
2. `Main` has a one-to-one relationship with `Metadata` and consolidates key information
3. `LoadAssociation` links fastq names to load names (many-to-many relationship)
4. Processing status is tracked in `Alignment`, `PostQC`, and `Ingest` models
5. All models are linked to `Metadata` through the `fastq_name` field

## Table Counts
- **Metadata**: 11,709 records
- **Main**: 11,709 records 
- **LoadAssociation**: 11,660 records
- **Alignment**: 11,660 records
- **PostQC**: 11,659 records
- **Ingest**: 11,660 records

This confirms that each fastq file in the Metadata table has a corresponding entry in the Main table. Most (but not all) also have corresponding entries in the processing tables. 