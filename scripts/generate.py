import json

# Load JSON file
with open("/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json", "r") as file:
    data = json.load(file)

# Output SQL file
output_sql_file = "study.sql"

# Open the SQL file for writing
with open(output_sql_file, "w") as sql_file:

    sql_file.write("-- SQL script to insert data from JSON\n\n")

    # Loop through each record in the JSON data
    for fastq_name, details in data.items():
        # Helper function to handle NA/null values
        def format_sql_value(val):
            if val in [None, "NA", ""]:
                return "NULL"
            return f"'{val}'"

        load_name = details.get("Load Name")
        if load_name in [None, "", "NA"]:
            continue

        library_prep_method = details.get("Library Prep Method")
        organism = details.get("Organism")
        study_set = details.get("Study Set", None)

        ingest_status = details.get("Ingest")
        alignment_status = details.get("Alignment")
        postqc_status = details.get("Post-Alignment")

        ingest_time = details.get("Ingest Time")
        alignment_time = details.get("Alignment Time")
        postqc_time = details.get("Post Alignment Time")

        fid_ingest = details.get("FID-Ingest")
        fid_alignment = details.get("FID-Alignment")
        fid_postqc = details.get("FID-Post-Alignment")

        # Format all fields safely
        f_fastq_name = format_sql_value(fastq_name)
        f_load_name = format_sql_value(load_name)
        f_library_prep_method = format_sql_value(library_prep_method)
        f_organism = format_sql_value(organism)
        f_studies = f"'[\"{study_set}\"]'" if study_set else "NULL"

        f_ingest_status = format_sql_value(ingest_status)
        f_alignment_status = format_sql_value(alignment_status)
        f_postqc_status = format_sql_value(postqc_status)

        f_ingest_time = format_sql_value(ingest_time)
        f_alignment_time = format_sql_value(alignment_time)
        f_postqc_time = format_sql_value(postqc_time)

        f_fid_ingest = format_sql_value(fid_ingest)
        f_fid_alignment = format_sql_value(fid_alignment)
        f_fid_postqc = format_sql_value(fid_postqc)

        # Prepare SQL INSERT statements
        sql_file.write(f"-- Inserting into metadata\n")
        sql_file.write(f"INSERT INTO metadata (fastq_name, load_name, library_prep_method_name, organism_name, studies)\n")
        sql_file.write(f"VALUES ({f_fastq_name}, {f_load_name}, {f_library_prep_method}, {f_organism}, {f_studies})\n")
        sql_file.write(f"ON CONFLICT (fastq_name) DO NOTHING;\n\n")

        sql_file.write(f"-- Inserting into load_association\n")
        sql_file.write(f"INSERT INTO load_association (load_name, fastq_name)\n")
        sql_file.write(f"VALUES ({f_load_name}, {f_fastq_name})\n")
        sql_file.write(f"ON CONFLICT DO NOTHING;\n\n")

        sql_file.write(f"-- Inserting into ingest\n")
        sql_file.write(f"INSERT INTO ingest (fastq_name, status_id, filestore_id, ingest_time)\n")
        sql_file.write(f"VALUES ({f_fastq_name}, {f_ingest_status}, {f_fid_ingest}, {f_ingest_time})\n")
        sql_file.write(f"ON CONFLICT (fastq_name) DO NOTHING;\n\n")

        sql_file.write(f"-- Inserting into alignment\n")
        sql_file.write(f"INSERT INTO alignment (fastq_name, status_id, filestore_id, alignment_time)\n")
        sql_file.write(f"VALUES ({f_fastq_name}, {f_alignment_status}, {f_fid_alignment}, {f_alignment_time})\n")
        sql_file.write(f"ON CONFLICT (fastq_name) DO NOTHING;\n\n")

        sql_file.write(f"-- Inserting into postqc\n")
        sql_file.write(f"INSERT INTO postqc (fastq_name, status_id, filestore_id, postqc_time)\n")
        sql_file.write(f"VALUES ({f_fastq_name}, {f_postqc_status}, {f_fid_postqc}, {f_postqc_time})\n")
        sql_file.write(f"ON CONFLICT (fastq_name) DO NOTHING;\n\n")

print(f"SQL script '{output_sql_file}' generated successfully.")
