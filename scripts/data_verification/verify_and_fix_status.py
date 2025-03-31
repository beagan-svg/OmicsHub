#!/usr/bin/env python
"""
OCS Database - Status Verification and Fix Tool

This script verifies and fixes status discrepancies between JSON data and
database records. It compares status values in the database with those in
the JSON file, displays current status counts, and allows the user to fix
any discrepancies interactively.

Usage:
    python scripts/data_verification/verify_and_fix_status.py

Features:
    - Displays current status counts in database and JSON
    - Interactive prompt for confirming fixes
    - Transaction-based updates to ensure database integrity
    - Detailed reporting of changes made

Requirements:
    - Django environment must be properly configured
    - JSON file must exist at the specified path
"""

import os
import json
import django
from datetime import datetime
import sys

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'database_ocs_project.settings')
django.setup()

from django.db import transaction
from viewer.models import Metadata, Alignment, PostQC, Ingest, Main
from django.db.models import Count

def parse_datetime(datetime_str):
    if datetime_str == "NA" or not datetime_str:
        return None
    try:
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None

def verify_and_fix_status():
    json_path = '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} does not exist")
        return
    
    print(f"Reading study data from {json_path}...")
    # Load the JSON data
    with open(json_path, 'r') as f:
        study_data = json.load(f)
    
    total_records = len(study_data)
    print(f"Found {total_records} records in study.json")
    
    # Get current status counts in the database
    print("\nCurrent status counts in database:")
    alignment_status_counts = Main.objects.values('alignment_status').annotate(count=Count('alignment_status')).order_by('alignment_status')
    for status in alignment_status_counts:
        print(f"Alignment - {status['alignment_status'] or 'NULL'}: {status['count']}")
    
    postqc_status_counts = Main.objects.values('postqc_status').annotate(count=Count('postqc_status')).order_by('postqc_status')
    for status in postqc_status_counts:
        print(f"PostQC - {status['postqc_status'] or 'NULL'}: {status['count']}")
    
    ingest_status_counts = Main.objects.values('ingest_status').annotate(count=Count('ingest_status')).order_by('ingest_status')
    for status in ingest_status_counts:
        print(f"Ingest - {status['ingest_status'] or 'NULL'}: {status['count']}")
    
    # Get status counts from study.json
    print("\nStatus counts in study.json:")
    alignment_json_counts = {}
    postqc_json_counts = {}
    ingest_json_counts = {}
    
    for data in study_data.values():
        alignment_status = data.get('Alignment')
        if alignment_status not in alignment_json_counts:
            alignment_json_counts[alignment_status] = 0
        alignment_json_counts[alignment_status] += 1
        
        postqc_status = data.get('Post-Alignment')
        if postqc_status not in postqc_json_counts:
            postqc_json_counts[postqc_status] = 0
        postqc_json_counts[postqc_status] += 1
        
        ingest_status = data.get('Ingest')
        if ingest_status not in ingest_json_counts:
            ingest_json_counts[ingest_status] = 0
        ingest_json_counts[ingest_status] += 1
    
    for status, count in sorted(alignment_json_counts.items()):
        print(f"Alignment - {status or 'NULL'}: {count}")
    for status, count in sorted(postqc_json_counts.items()):
        print(f"PostQC - {status or 'NULL'}: {count}")
    for status, count in sorted(ingest_json_counts.items()):
        print(f"Ingest - {status or 'NULL'}: {count}")
    
    # Ask user if they want to fix the discrepancies
    answer = input("\nDo you want to fix status discrepancies? (y/n): ")
    if answer.lower() != 'y':
        print("Operation cancelled.")
        return
    
    # Process and update records
    processed = 0
    updated = 0
    skipped = 0
    errors = 0
    
    for fastq_name, data in study_data.items():
        try:
            # Check if this fastq exists in our database
            try:
                metadata = Metadata.objects.get(fastq_name=fastq_name)
            except Metadata.DoesNotExist:
                skipped += 1
                continue
            
            # Get the main record
            try:
                main_record = Main.objects.get(fastq_name=metadata)
            except Main.DoesNotExist:
                print(f"Error: Main record not found for {fastq_name}")
                skipped += 1
                continue
            
            # Compare and update statuses
            changed = False
            
            # Update alignment status
            json_alignment = data.get('Alignment')
            if json_alignment and main_record.alignment_status != json_alignment:
                with transaction.atomic():
                    # Update Main table
                    main_record.alignment_status = json_alignment
                    main_record.save(update_fields=['alignment_status'])
                    
                    # Update or create Alignment record
                    Alignment.objects.update_or_create(
                        fastq_name=metadata,
                        defaults={
                            'status_id': json_alignment,
                            'end_time': parse_datetime(data.get('Alignment Time')),
                            'fid': data.get('FID-Alignment', '')
                        }
                    )
                changed = True
                print(f"Updated alignment status for {fastq_name}: {main_record.alignment_status} -> {json_alignment}")
            
            # Update postQC status
            json_postqc = data.get('Post-Alignment')
            if json_postqc and main_record.postqc_status != json_postqc:
                with transaction.atomic():
                    # Update Main table
                    main_record.postqc_status = json_postqc
                    main_record.save(update_fields=['postqc_status'])
                    
                    # Update or create PostQC record
                    PostQC.objects.update_or_create(
                        fastq_name=metadata,
                        defaults={
                            'status_id': json_postqc,
                            'end_time': parse_datetime(data.get('Post Alignment Time')),
                            'fid': data.get('FID-Post-Alignment', '')
                        }
                    )
                changed = True
                print(f"Updated postQC status for {fastq_name}: {main_record.postqc_status} -> {json_postqc}")
            
            # Update ingest status
            json_ingest = data.get('Ingest')
            if json_ingest and main_record.ingest_status != json_ingest:
                with transaction.atomic():
                    # Update Main table
                    main_record.ingest_status = json_ingest
                    main_record.save(update_fields=['ingest_status'])
                    
                    # Update or create Ingest record
                    Ingest.objects.update_or_create(
                        fastq_name=metadata,
                        defaults={
                            'status_id': json_ingest,
                            'end_time': parse_datetime(data.get('Ingest Time')),
                            'fid': data.get('FID-Ingest', '')
                        }
                    )
                changed = True
                print(f"Updated ingest status for {fastq_name}: {main_record.ingest_status} -> {json_ingest}")
            
            if changed:
                updated += 1
            
            processed += 1
            if processed % 500 == 0:
                print(f"Processed {processed}/{total_records} records...")
                
        except Exception as e:
            errors += 1
            print(f"Error processing {fastq_name}: {e}")
            if errors > 20:
                print("Too many errors, stopping process.")
                break
    
    # Print summary
    print("\nStatus update complete!")
    print(f"Records processed: {processed}")
    print(f"Records updated: {updated}")
    print(f"Records skipped: {skipped}")
    print(f"Errors: {errors}")
    
    # Print updated status counts
    print("\nUpdated status counts in database:")
    alignment_status_counts = Main.objects.values('alignment_status').annotate(count=Count('alignment_status')).order_by('alignment_status')
    for status in alignment_status_counts:
        print(f"Alignment - {status['alignment_status'] or 'NULL'}: {status['count']}")
    
    postqc_status_counts = Main.objects.values('postqc_status').annotate(count=Count('postqc_status')).order_by('postqc_status')
    for status in postqc_status_counts:
        print(f"PostQC - {status['postqc_status'] or 'NULL'}: {status['count']}")
    
    ingest_status_counts = Main.objects.values('ingest_status').annotate(count=Count('ingest_status')).order_by('ingest_status')
    for status in ingest_status_counts:
        print(f"Ingest - {status['ingest_status'] or 'NULL'}: {status['count']}")

if __name__ == "__main__":
    verify_and_fix_status() 