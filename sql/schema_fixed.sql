-- Table: metadata
CREATE TABLE metadata
(
    fastq_name VARCHAR(255) PRIMARY KEY,
    organism_name VARCHAR(255),
    library_prep_method_name VARCHAR(255),
    studies TEXT[]
);

-- Table: load_association
CREATE TABLE load_association
(
    fastq_name VARCHAR(255),
    load_name VARCHAR(255),
    PRIMARY KEY (fastq_name, load_name)
);

-- Table: alignment
CREATE TABLE alignment
(
    fastq_name VARCHAR(255) PRIMARY KEY,
    status_id VARCHAR(50) CHECK (status_id IN ('NOT COMPLETED', 'COMPLETED', 'FAILED', 'IN_PROGRESS')),
    start_time TIMESTAMP WITH TIME ZONE NULL,
    end_time TIMESTAMP WITH TIME ZONE NULL
);

-- Table: postqc
CREATE TABLE postqc
(
    fastq_name VARCHAR(255) PRIMARY KEY,
    status_id VARCHAR(50) CHECK (status_id IN ('NOT COMPLETED', 'COMPLETED', 'FAILED', 'IN_PROGRESS')),
    start_time TIMESTAMP WITH TIME ZONE NULL,
    end_time TIMESTAMP WITH TIME ZONE NULL
);

-- Table: ingest
-- Tracks data ingestion status and results
CREATE TABLE ingest
(
    fastq_name VARCHAR(255) PRIMARY KEY,
    status_id VARCHAR(50) CHECK (status_id IN ('NOT COMPLETED', 'COMPLETED', 'FAILED', 'IN_PROGRESS')),
    start_time TIMESTAMP WITH TIME ZONE NULL,
    end_time TIMESTAMP WITH TIME ZONE NULL
);

-- Table: main
CREATE TABLE main
(
    fastq_name VARCHAR(255) PRIMARY KEY,
    study_set VARCHAR(255),
    load_name VARCHAR(255),
    library_prep_method VARCHAR(255),
    organism VARCHAR(255),
    alignment_status VARCHAR(50),
    postqc_status VARCHAR(50),
    ingest_status VARCHAR(50)
);

-- Indexing metadata fields that might be frequently queried
CREATE INDEX idx_metadata_status_id ON alignment(status_id);
CREATE INDEX idx_metadata_organism_name ON metadata(organism_name); 