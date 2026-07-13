-- Reload the OCS sample tables from the batch_csv exports.
--
-- Merge rule (study.csv primary + batch names):
--   * study.csv is the authoritative source for study set / statuses / times / FIDs.
--   * Batch Name comes from the mtx/rtx/rfx exports (study.csv and atx have none).
--   * fastq rows present only in a batch export are added on top.
--
-- Mapping follows the existing DB convention: the single "<stage> Time"
-- column is stored in start_time (end_time stays NULL), fid is set, and
-- retry_count is 0. Blank status -> no status row + NULL status in main.
-- "NA"/blank time and FID values -> NULL.
--
-- Run a dry run first (rolls back, prints would-be counts):
--   psql -v do_commit=false -f sql/load_from_csv.sql
-- Then for real:
--   psql -v do_commit=true  -f sql/load_from_csv.sql

\set ON_ERROR_STOP on

BEGIN;

-- ---- staging ---------------------------------------------------------------
CREATE TEMP TABLE stg_study (
    fastq text, study_set text, load_name text, library_prep text, organism text,
    ingest text, alignment text, postqc text,
    ingest_time text, alignment_time text, postqc_time text,
    fid_ingest text, fid_alignment text, fid_postqc text
) ON COMMIT DROP;
\copy stg_study FROM '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs_tracker/batch_csv/study.csv' WITH (FORMAT csv, HEADER true)

CREATE TEMP TABLE stg_batch (
    fastq text, study_set text, batch_name text, organism text, load_name text, library_prep text,
    ingest text, alignment text, postqc text,
    ingest_time text, alignment_time text, postqc_time text,
    fid_ingest text, fid_alignment text, fid_postqc text
) ON COMMIT DROP;
\copy stg_batch FROM '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs_tracker/batch_csv/mtx_ocs_status.csv' WITH (FORMAT csv, HEADER true)
\copy stg_batch FROM '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs_tracker/batch_csv/rtx_status.csv' WITH (FORMAT csv, HEADER true)
\copy stg_batch FROM '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs_tracker/batch_csv/rfx_ocs_status.csv' WITH (FORMAT csv, HEADER true)

CREATE TEMP TABLE stg_atx (
    fastq text, organism text, load_name text, library_prep text,
    ingest text, ingest_time text
) ON COMMIT DROP;
\copy stg_atx FROM '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs_tracker/batch_csv/atx_status.csv' WITH (FORMAT csv, HEADER true)

-- ---- merge into one row per fastq ------------------------------------------
CREATE TEMP TABLE stg_all (
    fastq text PRIMARY KEY, study_set text, batch_name text, organism text,
    load_name text, library_prep text,
    ingest text, alignment text, postqc text,
    ingest_time text, alignment_time text, postqc_time text,
    fid_ingest text, fid_alignment text, fid_postqc text,
    has_align boolean NOT NULL
) ON COMMIT DROP;

-- study.csv wins on conflict; it carries alignment/post-align columns.
INSERT INTO stg_all
SELECT fastq, study_set, NULL, organism, load_name, library_prep,
       ingest, alignment, postqc, ingest_time, alignment_time, postqc_time,
       fid_ingest, fid_alignment, fid_postqc, true
FROM stg_study
ON CONFLICT (fastq) DO NOTHING;

-- fastqs only in the mtx/rtx/rfx exports.
INSERT INTO stg_all
SELECT fastq, study_set, batch_name, organism, load_name, library_prep,
       ingest, alignment, postqc, ingest_time, alignment_time, postqc_time,
       fid_ingest, fid_alignment, fid_postqc, true
FROM stg_batch
ON CONFLICT (fastq) DO NOTHING;

-- fastqs only in the atx export (ingest only, no alignment/post-align).
INSERT INTO stg_all (fastq, organism, load_name, library_prep, ingest, ingest_time, has_align)
SELECT fastq, organism, load_name, library_prep, ingest, ingest_time, false
FROM stg_atx
ON CONFLICT (fastq) DO NOTHING;

-- Batch Name comes only from the mtx/rtx/rfx exports.
UPDATE stg_all a
SET batch_name = b.batch_name
FROM stg_batch b
WHERE a.fastq = b.fastq;

-- ---- wipe + reload ---------------------------------------------------------
TRUNCATE alignment, postqc, ingest, load_association, main, metadata RESTART IDENTITY CASCADE;
TRUNCATE running_jobs, queue_jobs, failed_jobs, completed_jobs, in_progress_samples RESTART IDENTITY;

INSERT INTO metadata (fastq_name, organism_common_name, library_prep_method_name, studies, batch_name_from_vendor)
SELECT fastq, NULLIF(organism,''), NULLIF(library_prep,''), NULLIF(study_set,''), NULLIF(batch_name,'')
FROM stg_all;

INSERT INTO main (fastq_name_id, study_set, library_prep_method, organism, alignment_status, postqc_status, ingest_status)
SELECT fastq, NULLIF(study_set,''), NULLIF(library_prep,''), NULLIF(organism,''),
       NULLIF(alignment,''), NULLIF(postqc,''), NULLIF(ingest,'')
FROM stg_all;

INSERT INTO ingest (fastq_name_id, status_id, start_time, end_time, fid)
SELECT fastq, ingest,
       NULLIF(NULLIF(ingest_time,''),'NA')::timestamptz, NULL,
       NULLIF(NULLIF(fid_ingest,''),'NA')
FROM stg_all
WHERE NULLIF(ingest,'') IS NOT NULL;

INSERT INTO alignment (fastq_name_id, status_id, start_time, end_time, fid, demand_id, retry_count)
SELECT fastq, alignment,
       NULLIF(NULLIF(alignment_time,''),'NA')::timestamptz, NULL,
       NULLIF(NULLIF(fid_alignment,''),'NA'), NULL, 0
FROM stg_all
WHERE has_align AND NULLIF(alignment,'') IS NOT NULL;

INSERT INTO postqc (fastq_name_id, status_id, start_time, end_time, fid, demand_id, retry_count)
SELECT fastq, postqc,
       NULLIF(NULLIF(postqc_time,''),'NA')::timestamptz, NULL,
       NULLIF(NULLIF(fid_postqc,''),'NA'), NULL, 0
FROM stg_all
WHERE has_align AND NULLIF(postqc,'') IS NOT NULL;

INSERT INTO load_association (load_name, fastq_name_id)
SELECT NULLIF(load_name,''), fastq
FROM stg_all
WHERE NULLIF(load_name,'') IS NOT NULL;

-- ---- report ----------------------------------------------------------------
\echo '--- row counts after load ---'
SELECT 'metadata' AS tbl, count(*) FROM metadata
UNION ALL SELECT 'main', count(*) FROM main
UNION ALL SELECT 'ingest', count(*) FROM ingest
UNION ALL SELECT 'alignment', count(*) FROM alignment
UNION ALL SELECT 'postqc', count(*) FROM postqc
UNION ALL SELECT 'load_association', count(*) FROM load_association
ORDER BY tbl;

\if :do_commit
    COMMIT;
    \echo '*** COMMITTED ***'
\else
    ROLLBACK;
    \echo '*** DRY RUN - rolled back ***'
\endif
