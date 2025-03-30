import json
import os
from datetime import datetime
import pytz
import re
from collections import defaultdict
import subprocess
import csv

def normalize_timestamp(ts_str):
    if not ts_str:
        return None
    try:
        # Handle database format (local timezone)
        if ' ' in ts_str and ('-07' in ts_str or '-08' in ts_str):
            # Convert 2-digit timezone to 4-digit timezone
            ts_str = re.sub(r'(-0[78])$', r'\g<1>00', ts_str)
            # Convert to UTC
            # Handle both formats: with and without microseconds
            if '.' in ts_str:
                dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S.%f%z')
            else:
                dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S%z')
            return dt.astimezone(pytz.UTC).isoformat()
        # Handle JSON format (already UTC)
        elif 'T' in ts_str and '+00:00' in ts_str:
            return ts_str
        else:
            return ts_str
    except Exception as e:
        print(f"Error parsing timestamp {ts_str}: {e}")
        return None

def normalize_value(val):
    if val is None or val == '' or (isinstance(val, str) and not val.strip()):
        return None
    return val

def extract_study_set(studies_str):
    if not studies_str:
        return None
    try:
        studies_data = json.loads(studies_str)
        if isinstance(studies_data, dict):
            return studies_data.get('Study Set')
        elif isinstance(studies_data, list):
            # If it's a list, try to find a dict with Study Set
            for item in studies_data:
                if isinstance(item, dict) and 'Study Set' in item:
                    return item['Study Set']
        return None
    except Exception as e:
        print(f"Error parsing studies JSON: {e}")
        return None

print("Reading JSON file...")
# Read JSON file
with open('/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json', 'r') as f:
    json_data = json.load(f)

# Create a dictionary of JSON data
json_records = {}
for fastq_name, record in json_data.items():
    json_records[fastq_name] = {
        'ingest_time': record.get('Ingest Time'),
        'alignment_time': record.get('Alignment Time'),
        'postqc_time': record.get('Post Alignment Time'),
        'organism': normalize_value(record.get('Organism')),
        'library_prep_method': normalize_value(record.get('Library Prep Method')),
        'study_set': normalize_value(record.get('Study Set'))
    }

print("Getting database records...")
# Get database records using psql command
try:
    # Use psql to export data to CSV
    cmd = """psql prod_ocs -c "COPY (
        SELECT 
            m.fastq_name,
            m.organism_name,
            m.library_prep_method_name,
            m.studies,
            i.start_time as ingest_time,
            a.start_time as alignment_time,
            p.start_time as postqc_time
        FROM viewer_metadata m
        LEFT JOIN viewer_ingest i ON m.fastq_name = i.fastq_name_id
        LEFT JOIN viewer_alignment a ON m.fastq_name = a.fastq_name_id
        LEFT JOIN viewer_postqc p ON m.fastq_name = p.fastq_name_id
    ) TO STDOUT WITH CSV HEADER" > db_records.csv"""
    
    subprocess.run(cmd, shell=True, check=True)
    
    print("Processing database records...")
    # Read the CSV file
    db_records = {}
    with open('db_records.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            db_records[row['fastq_name']] = {
                'ingest_time': normalize_timestamp(row['ingest_time']) if row['ingest_time'] else None,
                'alignment_time': normalize_timestamp(row['alignment_time']) if row['alignment_time'] else None,
                'postqc_time': normalize_timestamp(row['postqc_time']) if row['postqc_time'] else None,
                'organism': normalize_value(row['organism_name']),
                'library_prep_method': normalize_value(row['library_prep_method_name']),
                'study_set': normalize_value(extract_study_set(row['studies']))
            }

except Exception as e:
    print(f"Error getting database records: {e}")
    exit(1)

print("Comparing records...")
# Compare records
mismatches = defaultdict(list)
only_in_json = set(json_records.keys()) - set(db_records.keys())
only_in_db = set(db_records.keys()) - set(json_records.keys())

# Check records that exist in both
for fastq_name in set(json_records.keys()) & set(db_records.keys()):
    json_rec = json_records[fastq_name]
    db_rec = db_records[fastq_name]
    
    # Compare each field
    for field in ['ingest_time', 'alignment_time', 'postqc_time', 'organism', 'library_prep_method', 'study_set']:
        if json_rec[field] != db_rec[field]:
            if field.endswith('_time'):
                # Only compare timestamps if both values exist
                if json_rec[field] and db_rec[field]:
                    mismatches[field].append(f"{fastq_name}: JSON={json_rec[field]}, DB={db_rec[field]}")
            else:
                # For non-timestamp fields, only report if they're not both None/empty
                if not (json_rec[field] is None and db_rec[field] is None):
                    mismatches[field].append(f"{fastq_name}: JSON={json_rec[field]}, DB={db_rec[field]}")

# Print results
print("\n=== Verification Report ===")
print(f"\nTotal records:")
print(f"  JSON: {len(json_records)}")
print(f"  Database: {len(db_records)}")

print(f"\nRecords only in JSON: {len(only_in_json)}")
if only_in_json:
    print("First 5 examples:")
    for fastq_name in list(only_in_json)[:5]:
        print(f"  - {fastq_name}")

print(f"\nRecords only in Database: {len(only_in_db)}")
if only_in_db:
    print("First 5 examples:")
    for fastq_name in list(only_in_db)[:5]:
        print(f"  - {fastq_name}")

print("\nField Mismatches:")
for field, field_mismatches in mismatches.items():
    if field_mismatches:
        print(f"\n{field} mismatches ({len(field_mismatches)}):")
        print("First 5 examples:")
        for mismatch in field_mismatches[:5]:
            print(f"  - {mismatch}")

if not mismatches and not only_in_json and not only_in_db:
    print("\nAll records match perfectly!") 