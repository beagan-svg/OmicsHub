-- Step 1: Change filestore_id to VARCHAR(255) in ingest
ALTER TABLE ingest 
ALTER COLUMN filestore_id TYPE VARCHAR(255) USING filestore_id::TEXT;

-- Step 2: Change filestore_id to VARCHAR(255) in alignment
ALTER TABLE alignment 
ALTER COLUMN filestore_id TYPE VARCHAR(255) USING filestore_id::TEXT;

-- Step 3: Change filestore_id to VARCHAR(255) in postqc
ALTER TABLE postqc 
ALTER COLUMN filestore_id TYPE VARCHAR(255) USING filestore_id::TEXT;
