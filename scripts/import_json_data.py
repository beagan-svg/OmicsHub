import json
import psycopg2
from psycopg2.extras import Json

def import_data():
    try:
        # Connect to the database
        conn = psycopg2.connect(dbname='prod_ocs')
        cur = conn.cursor()

        # Read the JSON file
        with open('/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json', 'r') as f:
            data_dict = json.load(f)

        success_count = 0
        error_count = 0

        for fastq_name, data in data_dict.items():
            try:
                # Insert into metadata table
                cur.execute("""
                    INSERT INTO metadata (fastq_name, organism_name, library_prep_method_name, studies)
                    VALUES (%s, %s, %s, %s)
                """, (
                    fastq_name,
                    data.get('Organism'),
                    data.get('Library Prep Method'),
                    [data.get('Study Set')] if data.get('Study Set') else []
                ))

                # Insert into alignment table
                cur.execute("""
                    INSERT INTO alignment (fastq_name, status_id, start_time, end_time)
                    VALUES (%s, %s, NULL, NULL)
                """, (
                    fastq_name,
                    data.get('Alignment', 'NOT COMPLETED')
                ))

                # Insert into postqc table
                cur.execute("""
                    INSERT INTO postqc (fastq_name, status_id, start_time, end_time)
                    VALUES (%s, %s, NULL, NULL)
                """, (
                    fastq_name,
                    data.get('Post-Alignment', 'NOT COMPLETED')
                ))

                # Insert into ingest table
                cur.execute("""
                    INSERT INTO ingest (fastq_name, status_id, start_time, end_time)
                    VALUES (%s, %s, NULL, NULL)
                """, (
                    fastq_name,
                    data.get('Ingest', 'NOT COMPLETED')
                ))

                # Insert into load_association table
                load_name = data.get('Load Name')
                if load_name:
                    cur.execute("""
                        INSERT INTO load_association (fastq_name, load_name)
                        VALUES (%s, %s)
                    """, (fastq_name, load_name))

                # Insert into main table
                cur.execute("""
                    INSERT INTO main (
                        fastq_name, study_set, load_name, library_prep_method,
                        organism, alignment_status, postqc_status, ingest_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    fastq_name,
                    data.get('Study Set'),
                    data.get('Load Name'),
                    data.get('Library Prep Method'),
                    data.get('Organism'),
                    data.get('Alignment', 'NOT COMPLETED'),
                    data.get('Post-Alignment', 'NOT COMPLETED'),
                    data.get('Ingest', 'NOT COMPLETED')
                ))

                success_count += 1
                conn.commit()

            except Exception as e:
                print(f"Error processing record {fastq_name}: {str(e)}")
                error_count += 1
                conn.rollback()
                continue

        print(f"Import completed. Success: {success_count}, Errors: {error_count}")

    except Exception as e:
        print(f"Database connection error: {str(e)}")

    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    import_data() 