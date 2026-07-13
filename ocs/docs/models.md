# OCS Database Models

Database models for the OCS Database Viewer (`ocs` app). Defined in
[`ocs/models.py`](../models.py).

There are two groups:

- **Sample data** — `Metadata`, `Main`, `Alignment`, `PostQC`, `Ingest`,
  `LoadAssociation`. These mirror existing database tables/views.
- **Pipeline state** — `QueueJobs`, `QueueControl`, `RunningJob`, `FailedJob`,
  `CompletedJob`, plus the user-facing `UserPreferences`. These are managed by
  this app and track a sample's journey through alignment / post-QC.

---

## Sample data models

### Metadata
Core per-sample record. Primary key is `fastq_name`.

| Field | Type | Notes |
|-------|------|-------|
| `fastq_name` | CharField | **Primary key** |
| `organism_name` | CharField | Scientific name |
| `organism_common_name` | CharField | e.g. "human", "mouse" |
| `library_prep_method_name` | CharField | |
| `library_prep_method_id` | BigIntegerField | |
| `library_prep_name` | CharField | |
| `alignment_method` | CharField | |
| `studies` | CharField | |
| `batch_name_from_vendor` | CharField | Used to derive workflow (MTX/RTX/ATX) |
| `amplification_id` / `amplification_name` | BigIntegerField / CharField | |
| `cell_capture` | IntegerField | |
| `cell_prep_type` | CharField | |
| `sample_id` / `sample_name` / `sample_type` | BigIntegerField / CharField / CharField | |
| `sequencing_vendor` | CharField | |

### Main
A database **view** joining metadata with current status. `managed = False`
(Django never creates/alters this table), default ordering by `fastq_name`.

| Field | Type | Notes |
|-------|------|-------|
| `fastq_name` | OneToOneField(Metadata) | **Primary key**, `related_name='main'` |
| `study_set` | CharField | |
| `library_prep_method` | CharField | |
| `organism` | CharField | |
| `ingest_status` | CharField | |
| `alignment_status` | CharField | |
| `postqc_status` | CharField | |

### Alignment / PostQC
Per-stage processing status. Identical shape; one table each.

| Field | Type | Notes |
|-------|------|-------|
| `fastq_name` | OneToOneField(Metadata) | **Primary key** |
| `status_id` | CharField | e.g. SUBMITTED, IN_PROGRESS, COMPLETED, FAILED, ABORTED |
| `start_time` / `end_time` | DateTimeField | nullable |
| `fid` | CharField | nullable |
| `demand_id` | CharField | OCS demand id, nullable |
| `retry_count` | IntegerField | default 0 |

### Ingest
Ingestion status (no `demand_id` / `retry_count`).

| Field | Type | Notes |
|-------|------|-------|
| `fastq_name` | OneToOneField(Metadata) | **Primary key** |
| `status_id` | CharField | |
| `start_time` / `end_time` | DateTimeField | nullable |
| `fid` | CharField | nullable |

### LoadAssociation
Maps a sample to load name(s) — **many per sample**.

| Field | Type | Notes |
|-------|------|-------|
| `fastq_name` | ForeignKey(Metadata) | |
| `load_name` | CharField | |

---

## Pipeline-state models

A sample submitted for processing moves through these tables:

```
QueueJobs (Ready/Pending)
     │  backend processor submits the next Ready job
     ▼
RunningJob ──► CompletedJob   (status COMPLETED)
           └─► FailedJob       (status FAILED / ABORTED)
```

`QueueControl` gates whether the backend processor runs and how often.

### QueueJobs
The single shared submission queue (`db_table='queue_jobs'`, ordered `-time`).

| Field | Type | Notes |
|-------|------|-------|
| `fastq_name` | CharField | **Primary key** |
| `alignment_command` / `postqc_command` | TextField | nullable |
| `time` | DateTimeField | default `timezone.now`; also the processing order |
| `status` | CharField | default `Ready` (Ready / Pending / PROCESSING / Running) |
| `user` | ForeignKey(auth.User) | owner; `on_delete=SET_NULL`, nullable. Regular users may only remove their own rows |

### QueueControl
Singleton (`pk=1`) controlling the backend processor.

| Field | Type | Notes |
|-------|------|-------|
| `state` | CharField | `running` / `paused` / `stopped` (default `running`) |
| `interval_minutes` | PositiveIntegerField | default 3; the shared auto-submit interval |
| `last_processed_at` | DateTimeField | global-timer anchor, nullable |
| `updated_at` | DateTimeField | `auto_now` |
| `updated_by` | ForeignKey(auth.User) | `on_delete=SET_NULL`, nullable |

Use `QueueControl.get()` to fetch/create the singleton.

### RunningJob / FailedJob
In-flight and failed jobs — identical shape.

| Field | Type | Notes |
|-------|------|-------|
| `fastq_name` | CharField | **Primary key** |
| `alignment_command` / `postqc_command` | TextField | nullable |
| `time` | DateTimeField | `auto_now_add` |
| `alignment_attempts` / `postqc_attempts` | IntegerField | default 0 |
| `alignment_demand_id` / `postqc_demand_id` | CharField | OCS demand ids, nullable |

### CompletedJob
Terminal record for a finished sample (`db_table='completed_jobs'`).

| Field | Type | Notes |
|-------|------|-------|
| `fastq_name` | CharField | **Primary key** |
| `alignment_command` / `postqc_command` | TextField | nullable |
| `alignment_attempts` / `postqc_attempts` | IntegerField | default 0 |
| `alignment_demand_id` / `postqc_demand_id` | CharField | nullable |
| `alignment_status` / `postqc_status` | CharField | choices: Completed / Failed / Cancelled |
| `alignment_start_time` / `alignment_end_time` | DateTimeField | nullable |
| `postqc_start_time` / `postqc_end_time` | DateTimeField | nullable |

---

## UserPreferences
One row **per user** (`db_table='user_preferences'`). Settings follow the user
across devices (loaded/saved via `/api/preferences/`).

| Field | Type | Notes |
|-------|------|-------|
| `user` | OneToOneField(auth.User) | **Primary key**, `related_name='preferences'` |
| `column_settings` | JSONField | samples-browser column visibility |
| `filter_preferences` | JSONField | saved search / filters / filter mode |
| `theme` | CharField | light / dark / auto |
| `default_page_size` | IntegerField | 10 / 25 / 50 / 100 |
| `auto_refresh_enabled` | BooleanField | |
| `updated_at` | DateTimeField | `auto_now` |

---

## Relationships

```
Metadata (fastq_name)
    ├── One-to-One  → Main        (related_name='main')
    ├── One-to-One  → Alignment
    ├── One-to-One  → PostQC
    ├── One-to-One  → Ingest
    └── One-to-Many → LoadAssociation

auth.User
    ├── One-to-One  → UserPreferences (related_name='preferences')
    └── One-to-Many → QueueJobs        (owner)
```

`QueueJobs`, `RunningJob`, `FailedJob`, and `CompletedJob` are keyed by
`fastq_name` (string) and are not FK-linked to `Metadata`; they are correlated by
`fastq_name` value.

## Usage examples

```python
from ocs.models import Metadata, QueueControl

# Sample status (via the Main view)
sample = Metadata.objects.get(fastq_name='SAMPLE1_MX123456')
alignment_status = sample.main.alignment_status
load_names = [la.load_name for la in sample.loadassociation_set.all()]

# Queue processor state
control = QueueControl.get()
is_running = control.state == 'running'
```

Job (de)serialization for the Job Monitor / Pipeline Checkout lives in
[`ocs/serializers.py`](../serializers.py); status-transition logic lives in
[`ocs/pipeline_utils.py`](../pipeline_utils.py).
