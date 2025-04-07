#!/usr/bin/env python
"""
OCS Database - Vendor Data Importer

This script imports data from vendor CSV files (isilon.csv, nwgc.csv, nygc.csv) into the database.
It reads each CSV file and updates or creates corresponding database entries in the Metadata model.

Features:
    - Import data from multiple vendor sources (isilon, nwgc, nygc)
    - Update existing records or create new ones
    - Handle data type conversions and validation
    - Dry run mode for testing without modifying the database
    - Detailed logging and error reporting

Usage:
    python scripts/data_import/import_vendor_data.py [options]
    
Options:
    --source SOURCE    Specify which source to import (isilon, nwgc, nygc, sample, all)
    --clear            Clear existing data before import (default: False)
    --dry-run          Simulate import without making changes to the database
    --debug            Enable debug logging

Example:
    python scripts/data_import/import_vendor_data.py --source isilon
    python scripts/data_import/import_vendor_data.py --source all --dry-run
"""

import os
import sys
import argparse
import logging
from typing import Dict, Optional, List, Any

# Import utility modules
# Add the project root directory to the Python path to ensure imports work
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import utility functions
from scripts.utilities.db_utils import setup_django_env, validate_field, get_db_stats
from scripts.utilities.file_utils import get_data_dir, load_csv_data, validate_file_exists

# Setup Django environment
setup_django_env()

# Now we can import Django models
from django.db import transaction
from viewer.models import Metadata, Main, Alignment, Ingest, PostQC, LoadAssociation

def process_csv_file(csv_path: str, source_name: str, dry_run: bool = False) -> Dict[str, int]:
    """
    Process a CSV file and import its data into the database.
    
    Args:
        csv_path: Path to the CSV file
        source_name: Name of the data source (for logging)
        dry_run: Whether to simulate the import without making changes
        
    Returns:
        Dictionary with statistics about the import
    """
    if not validate_file_exists(csv_path):
        logger.error(f"Error: {csv_path} does not exist")
        return {'processed': 0, 'created': 0, 'updated': 0, 'errors': 0}
    
    logger.info(f"Processing {source_name} data from: {csv_path}")
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made to the database")
    
    stats = {
        'processed': 0,
        'created': 0,
        'updated': 0,
        'errors': 0
    }
    
    try:
        # Load CSV data
        csv_data = load_csv_data(csv_path)
        
        # Process each row
        for row in csv_data:
            stats['processed'] += 1
            
            # Skip database operations in dry run mode
            if dry_run:
                if stats['processed'] % 100 == 0 or stats['processed'] < 10:
                    logger.info(f"Would process record {stats['processed']}: {row.get('Fastq Name', 'unknown')}")
                continue
            
            try:
                process_record(row, stats)
                
                # Log progress
                if stats['processed'] % 100 == 0 or stats['processed'] < 10:
                    logger.info(f"Processed record {stats['processed']}: {row.get('Fastq Name', 'unknown')}")
                    
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error processing row {stats['processed']}: {e}")
    
    except Exception as e:
        logger.error(f"Error processing file {csv_path}: {e}")
        stats['errors'] += 1
    
    logger.info(f"Total records processed from {source_name}: {stats['processed']}")
    logger.info(f"Records created: {stats['created']}")
    logger.info(f"Records updated: {stats['updated']}")
    logger.info(f"Errors: {stats['errors']}")
    
    return stats

def process_record(row: Dict[str, str], stats: Dict[str, int]) -> None:
    """
    Process a single record from a CSV file.
    
    Args:
        row: Dictionary containing the record data
        stats: Dictionary to update with processing statistics
    """
    with transaction.atomic():
        fastq_name = row.get('Fastq Name')
        if not fastq_name:
            logger.warning(f"Skipping row - missing Fastq Name")
            stats['errors'] += 1
            return
        
        # Prepare default values with proper validation
        defaults = {
            'organism_common_name': row.get('Organism Common Name', ''),
            'organism_name': row.get('Organism Name', ''),
            'library_prep_method_name': row.get('Library Prep Method', ''),
            'studies': row.get('Study Set', ''),
            'alignment_method': row.get('Alignment Method', ''),
            'amplification_name': row.get('Amplification', ''),
            'batch_name': row.get('Batch Name', ''),
            'batch_name_from_vendor': row.get('Batch Name From Vendor', ''),
            'cell_prep_type': row.get('Cell Prep Type', ''),
            'library_prep_name': row.get('Library Prep Name', ''),
            'sample_name': row.get('Sample Name', ''),
            'sample_type': row.get('Sample Type', ''),
            'sequencing_vendor': row.get('Sequencing Vendor', '')
        }
        
        # Handle numeric fields separately with validation
        numeric_fields = {
            'amplification_id': row.get('Amplification ID', None),
            'cell_capture': row.get('Cell Capture', None),
            'library_prep_method_id': row.get('Library Prep Method ID', None),
            'sample_id': row.get('Sample ID', None),
        }
        
        for field, value in numeric_fields.items():
            defaults[field] = validate_field(Metadata, field, value)
        
        try:
            # Try to find existing record
            metadata, created = Metadata.objects.get_or_create(
                fastq_name=fastq_name,
                defaults=defaults
            )
            
            # If record already exists, update it
            if not created:
                # Only update non-empty values from CSV
                for field, value in defaults.items():
                    if value:
                        setattr(metadata, field, value)
                
                for field, value in numeric_fields.items():
                    validated_value = validate_field(Metadata, field, value)
                    if validated_value is not None:
                        setattr(metadata, field, validated_value)
                
                metadata.save()
                stats['updated'] += 1
            else:
                stats['created'] += 1
            
            # Update or create Main record without overwriting status fields
            main, main_created = Main.objects.get_or_create(
                fastq_name=metadata,
                defaults={
                    'study_set': row.get('Study Set', ''),
                    'organism': row.get('Organism Name', ''),
                    'library_prep_method': row.get('Library Prep Method', '')
                }
            )
            
            if not main_created:
                # Only update if CSV has non-empty values
                if row.get('Study Set'):
                    main.study_set = row['Study Set']
                if row.get('Organism Name'):
                    main.organism = row['Organism Name']
                if row.get('Library Prep Method'):
                    main.library_prep_method = row['Library Prep Method']
                main.save()
                
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"Error processing {fastq_name}: {e}")
            raise

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Import vendor data from CSV files')
    parser.add_argument('--source', type=str, choices=['isilon', 'nwgc', 'nygc', 'sample', 'all'], 
                      default='all', help='Specify which source to import')
    parser.add_argument('--clear', action='store_true', help="Clear existing data before import")
    parser.add_argument('--dry-run', action='store_true', help='Simulate import without making changes')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Define CSV file paths
    csv_dir = get_data_dir('csv')
    csv_files = {
        'isilon': os.path.join(csv_dir, 'isilon.csv'),
        'nwgc': os.path.join(csv_dir, 'nwgc.csv'),
        'nygc': os.path.join(csv_dir, 'nygc.csv'),
        'sample': os.path.join(csv_dir, 'sample.csv')
    }
    
    # Clear existing data only if --clear flag is provided
    if args.clear and not args.dry_run:
        logger.warning("Clearing existing data...")
        Metadata.objects.all().delete()
        logger.info("Data cleared.")
    
    # Process selected CSV files
    total_stats = {
        'processed': 0,
        'created': 0,
        'updated': 0,
        'errors': 0
    }
    
    if args.source == 'all':
        for source, file_path in csv_files.items():
            if validate_file_exists(file_path):
                stats = process_csv_file(file_path, source, args.dry_run)
                for key in total_stats:
                    total_stats[key] += stats[key]
            else:
                logger.warning(f"Skipping {source} import: {file_path} does not exist.")
    else:
        file_path = csv_files[args.source]
        if validate_file_exists(file_path):
            stats = process_csv_file(file_path, args.source, args.dry_run)
            for key in total_stats:
                total_stats[key] += stats[key]
        else:
            logger.error(f"Error: {file_path} does not exist")
            return
    
    if not args.dry_run:
        logger.info("\nImport completed successfully!")
        logger.info(f"Total records processed: {total_stats['processed']}")
        logger.info(f"Total records created: {total_stats['created']}")
        logger.info(f"Total records updated: {total_stats['updated']}")
        logger.info(f"Total errors: {total_stats['errors']}")
        
        # Get current database stats
        db_stats = get_db_stats()
        logger.info(f"Records in database:")
        for model, count in db_stats.items():
            logger.info(f"  {model}: {count}")
    else:
        logger.info("\nDry run completed. No changes were made to the database.")
        logger.info(f"Total records that would be processed: {total_stats['processed']}")
        logger.info(f"Total records that would be created: {total_stats['created']}")
        logger.info(f"Total records that would be updated: {total_stats['updated']}")
        logger.info(f"Total errors: {total_stats['errors']}")

if __name__ == "__main__":
    main() 