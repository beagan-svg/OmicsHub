-- Table: metadata
CREATE TABLE metadata
(
    fastq_name VARCHAR(255) PRIMARY KEY,
    alignment_method VARCHAR(255),
    amplification_id BIGINT,
    amplification_name VARCHAR(255),
    batch_name VARCHAR(255),
    batch_name_from_vendor VARCHAR(255),
    cell_capture INT,
    cell_prep_type VARCHAR(255),
    library_prep_method_id BIGINT,
    library_prep_method_name VARCHAR(255),
    library_prep_name VARCHAR(255),
    load_name VARCHAR(255),
    organism_common_name VARCHAR(255),
    organism_name VARCHAR(255),
    sample_id BIGINT,
    sample_name VARCHAR(255),
    sample_type VARCHAR(255),
    sequencing_vendor VARCHAR(255),
    studies JSONB
    -- Store the list of studies as a JSON array
);

-- Table: load_association
CREATE TABLE load_association
(
    load_name VARCHAR(100) NOT NULL,
    fastq_name VARCHAR(100) NOT NULL,
    PRIMARY KEY (load_name, fastq_name),
    FOREIGN KEY (fastq_name) REFERENCES metadata(fastq_name) ON DELETE CASCADE
);

-- Table: alignment
CREATE TABLE alignment
(
    fastq_name VARCHAR(100) PRIMARY KEY,
    demand_id VARCHAR(50),
    status_id VARCHAR(20) CHECK (status_id IN ('pending', 'in_progress', 'completed', 'failed')),
    filestore_id VARCHAR(50),
    alignment_time TIMESTAMPTZ,
    FOREIGN KEY (fastq_name) REFERENCES metadata(fastq_name) ON DELETE CASCADE
);

-- Table: postqc
CREATE TABLE postqc
(
    fastq_name VARCHAR(100) PRIMARY KEY,
    demand_id VARCHAR(50),
    status_id VARCHAR(20) CHECK (status_id IN ('pending', 'in_progress', 'completed', 'failed')),
    filestore_id VARCHAR(50),
    postqc_time TIMESTAMPTZ,
    FOREIGN KEY (fastq_name) REFERENCES metadata(fastq_name) ON DELETE CASCADE
);

-- Table: ingest
-- Tracks data ingestion status and results
CREATE TABLE ingest
(
    fastq_name VARCHAR(100) PRIMARY KEY,
    demand_id VARCHAR(50),
    status_id VARCHAR(20) CHECK (status_id IN ('pending', 'in_progress', 'completed', 'failed')),
    filestore_id VARCHAR(50),
    ingest_time TIMESTAMPTZ,
    FOREIGN KEY (fastq_name) REFERENCES metadata(fastq_name) ON DELETE CASCADE
);

-- Table: main
CREATE TABLE main
(
    fastq_name VARCHAR(255) PRIMARY KEY,
    FOREIGN KEY (fastq_name) REFERENCES ingest(fastq_name) ON DELETE CASCADE,
    FOREIGN KEY (fastq_name) REFERENCES alignment(fastq_name) ON DELETE CASCADE,
    FOREIGN KEY (fastq_name) REFERENCES postqc(fastq_name) ON DELETE CASCADE,
    FOREIGN KEY (fastq_name) REFERENCES metadata(fastq_name) ON DELETE CASCADE,
    FOREIGN KEY (fastq_name) REFERENCES load_association(fastq_name) ON DELETE CASCADE
);

-- Table: queue
CREATE TABLE queue (
    fastq_name VARCHAR(255) PRIMARY KEY,
    alignment_command TEXT,
    postqc_command TEXT,
    time TIMESTAMPTZ DEFAULT NOW()
);

-- Table: in_progress_samples
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

-- Indexing metadata fields that might be frequently queried
CREATE INDEX idx_metadata_status_id ON alignment(status_id);
CREATE INDEX idx_metadata_organism_name ON metadata(organism_name);