import json
import psycopg2
from psycopg2.extras import RealDictCursor

def verify_load_associations():
    # Read study.json
    json_path = '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
    with open(json_path, 'r') as f:
        study_data = json.load(f)
    
    # Connect to database
    conn = psycopg2.connect(
        dbname="prod_ocs",
        user="postgres",
        password="postgres",
        host="localhost",
        port="5432"
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get database associations
    cur.execute("""
        SELECT m.fastq_name, la.load_name 
        FROM viewer_loadassociation la 
        JOIN viewer_metadata m ON la.fastq_name_id = m.fastq_name
    """)
    db_associations = {row['fastq_name']: row['load_name'] for row in cur.fetchall()}
    
    # Check for discrepancies
    missing_in_db = []
    missing_in_json = []
    mismatched = []
    
    # Check entries in study.json
    for fastq_name, record in study_data.items():
        load_name = record.get('Load Name')
        if load_name:
            if fastq_name not in db_associations:
                missing_in_db.append((fastq_name, load_name))
            elif db_associations[fastq_name] != load_name:
                mismatched.append((fastq_name, load_name, db_associations[fastq_name]))
    
    # Check entries in database
    for fastq_name in db_associations:
        if fastq_name not in study_data:
            missing_in_json.append((fastq_name, db_associations[fastq_name]))
    
    # Print results
    print(f"\nTotal entries in study.json with Load Name: {sum(1 for v in study_data.values() if v.get('Load Name'))}")
    print(f"Total entries in database: {len(db_associations)}")
    
    if missing_in_db:
        print("\nEntries in study.json but missing in database:")
        for fastq_name, load_name in missing_in_db[:5]:
            print(f"  {fastq_name} -> {load_name}")
        if len(missing_in_db) > 5:
            print(f"  ... and {len(missing_in_db) - 5} more")
    
    if missing_in_json:
        print("\nEntries in database but missing in study.json:")
        for fastq_name, load_name in missing_in_json[:5]:
            print(f"  {fastq_name} -> {load_name}")
        if len(missing_in_json) > 5:
            print(f"  ... and {len(missing_in_json) - 5} more")
    
    if mismatched:
        print("\nMismatched load names:")
        for fastq_name, json_load, db_load in mismatched[:5]:
            print(f"  {fastq_name}: study.json={json_load}, database={db_load}")
        if len(mismatched) > 5:
            print(f"  ... and {len(mismatched) - 5} more")
    
    if not (missing_in_db or missing_in_json or mismatched):
        print("\nAll load associations match between study.json and database!")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    verify_load_associations() 