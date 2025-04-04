#!/usr/bin/env python
"""
OCS Database - Vendor Data Importer

This script imports data from vendor CSV files (isilon.csv, nwgc.csv, nygc.csv) into the database.
It reads each CSV file and updates or creates corresponding database entries in the Metadata model.

Usage:
    python scripts/data_import/import_vendor_data.py [options]
    
Options:
    --source SOURCE    Specify which source to import (isilon, nwgc, nygc, all)
    --no-clear         Don't clear existing data before import
    --dry-run          Simulate import without making changes to the database

Requirements:
    - Django environment must be properly configured
    - CSV files must exist in the data/csv directory
"""

import os
import sys
import csv
import argparse
import django
from datetime import datetime

# Set up Django environment
# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.db import transaction
from viewer.models import Metadata, Main

def process_csv_file(csv_path, source_name, dry_run=False):
    """Process a CSV file and import its data into the database."""
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} does not exist")
        return 0
    
    print(f"Processing {source_name} data from: {csv_path}")
    if dry_run:
        print("DRY RUN MODE - No changes will be made to the database")
    
    count = 0
    updated = 0
    created = 0
    
    with open(csv_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            count += 1
            
            # Skip database operations in dry run mode
            if dry_run:
                if count % 100 == 0 or count < 10:  # Show only a few records in dry run
                    print(f"Would process record {count}: {row.get('Fastq Name', 'unknown')}")
                continue
            
            try:
                with transaction.atomic():
                    fastq_name = row.get('Fastq Name')
                    if not fastq_name:
                        print(f"Warning: Skipping row {count} - missing Fastq Name")
                        continue
                    
                    # Try to find existing record
                    metadata, created_flag = Metadata.objects.get_or_create(
                        fastq_name=fastq_name,
                        defaults={
                            'organism_name': row.get('Organism Name', ''),
                            'library_prep_method_name': row.get('Library Prep Method', ''),
                            'studies': row.get('Study Set', '')
                        }
                    )
                    
                    # If record already exists, update it
                    if not created_flag:
                        metadata.organism_name = row.get('Organism Name', '') or metadata.organism_name
                        metadata.library_prep_method_name = row.get('Library Prep Method', '') or metadata.library_prep_method_name
                        metadata.studies = row.get('Study Set', '') or metadata.studies
                        metadata.save()
                        updated += 1
                    else:
                        created += 1
                    
                    # Update or create Main record
                    main, main_created = Main.objects.get_or_create(
                        fastq_name=metadata,
                        defaults={
                            'study_set': row.get('Study Set', ''),
                            'organism': row.get('Organism Name', ''),
                            'library_prep_method': row.get('Library Prep Method', '')
                        }
                    )
                    
                    if not main_created:
                        main.study_set = row.get('Study Set', '') or main.study_set
                        main.organism = row.get('Organism Name', '') or main.organism
                        main.library_prep_method = row.get('Library Prep Method', '') or main.library_prep_method
                        main.save()
                    
                    # Log progress
                    if count % 100 == 0 or count < 10:
                        action = "Created" if created_flag else "Updated"
                        print(f"{action} record {count}: {fastq_name}")
                    
            except Exception as e:
                print(f"Error processing row {count}: {e}")
    
    print(f"Total records processed from {source_name}: {count}")
    print(f"Records created: {created}")
    print(f"Records updated: {updated}")
    return count

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Import vendor data from CSV files')
    parser.add_argument('--source', type=str, choices=['isilon', 'nwgc', 'nygc', 'sample', 'all'], 
                      default='all', help='Specify which source to import')
    parser.add_argument('--no-clear', action='store_true', help="Don't clear existing data before import")
    parser.add_argument('--dry-run', action='store_true', help='Simulate import without making changes')
    args = parser.parse_args()
    
    # Define CSV file paths
    data_dir = os.path.join(project_root, 'data', 'csv')
    csv_files = {
        'isilon': os.path.join(data_dir, 'isilon.csv'),
        'nwgc': os.path.join(data_dir, 'nwgc.csv'),
        'nygc': os.path.join(data_dir, 'nygc.csv'),
        'sample': os.path.join(data_dir, 'sample.csv')
    }
    
    # Clear existing data unless --no-clear flag is provided
    if not args.no_clear and not args.dry_run:
        print("Clearing existing data...")
        Metadata.objects.all().delete()
        print("Data cleared.")
    elif args.no_clear:
        print("Skipping data clearing (--no-clear flag provided)")
    
    # Process selected CSV files
    total_records = 0
    
    if args.source == 'all':
        for source, file_path in csv_files.items():
            if os.path.exists(file_path):
                total_records += process_csv_file(file_path, source, args.dry_run)
            else:
                print(f"Warning: {file_path} does not exist. Skipping {source} import.")
    else:
        file_path = csv_files[args.source]
        if os.path.exists(file_path):
            total_records += process_csv_file(file_path, args.source, args.dry_run)
        else:
            print(f"Error: {file_path} does not exist")
            return
    
    if not args.dry_run:
        print("\nImport completed successfully!")
        print(f"Total records processed: {total_records}")
        print(f"Total records in database: {Metadata.objects.count()}")
    else:
        print("\nDry run completed. No changes were made to the database.")
        print(f"Total records that would be processed: {total_records}")

if __name__ == "__main__":
    main() 