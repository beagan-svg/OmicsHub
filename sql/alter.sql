-- Step 1: Change filestore_id to VARCHAR(255) in ingest
ALTER TABLE ingest 
ALTER COLUMN filestore_id TYPE VARCHAR(255) USING filestore_id::TEXT;

-- Step 2: Change filestore_id to VARCHAR(255) in alignment
ALTER TABLE alignment 
ALTER COLUMN filestore_id TYPE VARCHAR(255) USING filestore_id::TEXT;

-- Step 3: Change filestore_id to VARCHAR(255) in postqc
ALTER TABLE postqc 
ALTER COLUMN filestore_id TYPE VARCHAR(255) USING filestore_id::TEXT;

-- Add Queue table
CREATE TABLE queue (
    fastq_name VARCHAR(255) PRIMARY KEY,
    alignment_command TEXT,
    postqc_command TEXT,
    time TIMESTAMPTZ DEFAULT NOW()
);

-- Add InProgressSamples table
CREATE TABLE in_progress_samples (
    fastq_name VARCHAR(255) PRIMARY KEY,
    alignment_command TEXT,
    postqc_command TEXT,
    time TIMESTAMPTZ DEFAULT NOW(),
    alignment_attempts INT DEFAULT 0,
    postqc_attempts INT DEFAULT 0,
    alignment_demand_id VARCHAR(255),
    postqc_demand_id VARCHAR(255)
);
