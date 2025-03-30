-- SQL script to insert data from JSON

-- Inserting into metadata
INSERT INTO metadata (fastq_name, load_name, library_prep_method_name, organism_name, studies) 
VALUES ('NY-AT26009-15', '2465_B09', '10xATAC_Mult', 'owl_monkey', '["HMBA_Cross_Species"]')
ON CONFLICT (fastq_name) DO NOTHING;

-- Inserting into load_association
INSERT INTO load_association (load_name, fastq_name) 
VALUES ('2465_B09', 'NY-AT26009-15')
ON CONFLICT DO NOTHING;

-- Inserting into ingest
INSERT INTO ingest (fastq_name, status_id, filestore_id, postqc_time) 
VALUES ('NY-AT26009-15', 'COMPLETED', '64bd64dc130ee1ecf3da6561f6a1078362567155', '2024-10-13T00:21:04.974000+00:00')
ON CONFLICT (fastq_name) DO NOTHING;

-- Inserting into alignment
INSERT INTO alignment (fastq_name, status_id, filestore_id, alignment_time) 
VALUES ('NY-AT26009-15', 'COMPLETED', '694239f8114e597d1fe1a63636284a70e9c6fbcb', '2024-10-13T09:02:27.848304+00:00')
ON CONFLICT (fastq_name) DO NOTHING;

-- Inserting into postqc
INSERT INTO postqc (fastq_name, status_id, filestore_id, postqc_time) 
VALUES ('NY-AT26009-15', 'COMPLETED', 'ee12a75f9b460646049b97ac30395fe43c5d223e', '2024-10-14T18:52:50.290881+00:00')
ON CONFLICT (fastq_name) DO NOTHING;
