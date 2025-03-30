#!/usr/bin/env python

import os
import json
import django
from datetime import datetime

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'database_ocs_project.settings')
django.setup()

from django.db import transaction
from viewer.models import Metadata, Alignment, PostQC, Ingest, LoadAssociation, Main

def parse_datetime(datetime_str):
    if datetime_str == "NA":
        return None
    try:
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None

def load_study_data():
    json_path = '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
    
    if not os.path.exists(json_path):
        print(f"Warning: {json_path} does not exist")
        return
    
    # Load the JSON data
    with open(json_path, 'r') as f:
        study_data = json.load(f)
    
    # Limit to first 20 records for testing
    limited_data = {}
    counter = 0
    for key, value in study_data.items():
        limited_data[key] = value
        counter += 1
        if counter >= 20:  # Only load 20 records
            break
    
    # Process each record
    count = 0
    for fastq_name, data in limited_data.items():
        try:
            with transaction.atomic():
                # Create metadata record
                metadata = Metadata.objects.create(
                    fastq_name=fastq_name,
                    organism_name=data.get('Organism'),
                    library_prep_method_name=data.get('Library Prep Method'),
                    studies=[data.get('Study Set')] if data.get('Study Set') else []
                )
                
                # Create main record
                Main.objects.create(
                    fastq_name=metadata,
                    study_set=data.get('Study Set'),
                    organism=data.get('Organism'),
                    library_prep_method=data.get('Library Prep Method'),
                    alignment_status=data.get('Alignment'),
                    postqc_status=data.get('Post-Alignment'),
                    ingest_status=data.get('Ingest')
                )
                
                # Create load association if Load Name exists
                if data.get('Load Name'):
                    LoadAssociation.objects.create(
                        fastq_name=metadata,
                        load_name=data['Load Name']
                    )
                
                # Create alignment record if data exists
                alignment_status = data.get('Alignment')
                if alignment_status:
                    Alignment.objects.create(
                        fastq_name=metadata,
                        status_id=alignment_status,
                        start_time=parse_datetime(data.get('Alignment Time')),
                        end_time=parse_datetime(data.get('Alignment Time')),  # Using same time for demo
                        fid=data.get('FID-Alignment', '')
                    )
                    print(f"Created Alignment record for {fastq_name}: {alignment_status}")
                
                # Create ingest record if data exists
                ingest_status = data.get('Ingest')
                if ingest_status:
                    Ingest.objects.create(
                        fastq_name=metadata,
                        status_id=ingest_status,
                        start_time=parse_datetime(data.get('Ingest Time')),
                        end_time=parse_datetime(data.get('Ingest Time')),  # Using same time for demo
                        fid=data.get('FID-Ingest', '')
                    )
                    print(f"Created Ingest record for {fastq_name}: {ingest_status}")
                
                # Create post-alignment QC record if data exists
                postqc_status = data.get('Post-Alignment')
                if postqc_status:
                    PostQC.objects.create(
                        fastq_name=metadata,
                        status_id=postqc_status,
                        start_time=parse_datetime(data.get('Post Alignment Time')),
                        end_time=parse_datetime(data.get('Post Alignment Time')),  # Using same time for demo
                        fid=data.get('FID-Post-Alignment', '')
                    )
                    print(f"Created PostQC record for {fastq_name}: {postqc_status}")
                
                count += 1
                print(f"Added record {count}: {fastq_name}")
                
        except Exception as e:
            print(f"Error processing {fastq_name}: {e}")
    
    print(f"Total records processed: {count}")
    print(f"Metadata records: {Metadata.objects.count()}")
    print(f"Main records: {Main.objects.count()}")
    print(f"LoadAssociation records: {LoadAssociation.objects.count()}")
    print(f"Alignment records: {Alignment.objects.count()}")
    print(f"PostQC records: {PostQC.objects.count()}")
    print(f"Ingest records: {Ingest.objects.count()}")

if __name__ == "__main__":
    # Clear existing data first
    print("Clearing existing data...")
    Metadata.objects.all().delete()
    
    # Load new data
    print("Loading study data...")
    load_study_data()
    print("Done!") 