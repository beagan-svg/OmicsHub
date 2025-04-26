#!/usr/bin/env python
"""
OCS Database - Study Data Loader

This script loads study data from a JSON file into the Django database.
It reads each record from the JSON file and creates corresponding database
entries for Metadata, Main, LoadAssociation, Alignment, Ingest, and PostQC models.

Features:
    - Import data from JSON file with entries for all model types
    - Update existing records or create new ones
    - Handle data type conversions and validation
    - Preserve existing data when needed (--no-clear option)
    - Dry run mode for testing without modifying the database
    - Detailed logging and error reporting

Usage:
    python scripts/data_import/load_study_data.py [options]
    
Options:
    --no-clear         Don't clear existing data before import
    --file PATH        Import from a specific JSON file
    --dry-run          Simulate import without making changes to the database
    --debug            Enable debug logging

Example:
    python scripts/data_import/load_study_data.py --no-clear
    python scripts/data_import/load_study_data.py --file /path/to/custom.json --dry-run
"""

import os
import sys
import argparse
import logging
from typing import Dict, Optional, Any, Tuple

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
from scripts.utilities.db_utils import setup_django_env, get_db_stats
from scripts.utilities.file_utils import load_json_data, validate_file_exists

# Setup Django environment
setup_django_env()

# Now we can import Django models
from django.db import transaction
from viewer.core.models import Metadata, Alignment, PostQC, Ingest, LoadAssociation, Main

def parse_datetime(datetime_str):
    """
    Parse a datetime string with consistent handling of edge cases.
    
    Args:
        datetime_str: Datetime string to parse
        
    Returns:
        Parsed datetime object or None
    """
    from scripts.utilities.db_utils import parse_datetime as util_parse_datetime
    return util_parse_datetime(datetime_str)

def load_study_data(json_path: Optional[str] = None, dry_run: bool = False) -> Dict[str, int]:
    """
    Load study data from a JSON file into the database.
    
    Args:
        json_path: Path to the JSON file (if None, uses default path)
        dry_run: Whether to simulate the import without making changes
        
    Returns:
        Dictionary with statistics about the import
    """
    if json_path is None:
        json_path = '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
    
    # Validate file exists
    if not validate_file_exists(json_path):
        logger.error(f"Error: {json_path} does not exist")
        return {
            'processed': 0,
            'metadata_created': 0,
            'metadata_updated': 0,
            'main_created': 0,
            'main_updated': 0,
            'load_association': 0,
            'alignment': 0,
            'postqc': 0,
            'ingest': 0,
            'errors': 0
        }
    
    logger.info(f"Loading data from: {json_path}")
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made to the database")
    
    # Load the JSON data
    try:
        study_data = load_json_data(json_path)
    except Exception as e:
        logger.error(f"Error loading JSON data: {e}")
        raise
    
    # Initialize stats
    stats = {
        'processed': 0,
        'metadata_created': 0,
        'metadata_updated': 0,
        'main_created': 0,
        'main_updated': 0,
        'load_association': 0,
        'alignment': 0,
        'postqc': 0,
        'ingest': 0,
        'errors': 0
    }
    
    # Process each record
    for fastq_name, data in study_data.items():
        try:
            # Skip database operations in dry run mode
            if dry_run:
                stats['processed'] += 1
                if stats['processed'] % 100 == 0 or stats['processed'] < 10:
                    logger.info(f"Would add/update record {stats['processed']}: {fastq_name}")
                continue
                
            # Process the record
            process_record(fastq_name, data, stats)
                
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"Error processing {fastq_name}: {e}")
    
    logger.info(f"Total records processed: {stats['processed']}")
    
    if not dry_run:
        # Get current database stats
        db_stats = get_db_stats()
        for model, count in db_stats.items():
            logger.info(f"{model.capitalize()} records: {count}")
    else:
        logger.info("Dry run completed. No changes were made to the database.")
    
    return stats

def process_record(fastq_name: str, data: Dict[str, Any], stats: Dict[str, int]) -> None:
    """
    Process a single record from the JSON data.
    
    Args:
        fastq_name: The fastq name (primary key)
        data: Dictionary containing the record data
        stats: Dictionary to update with processing statistics
    """
    with transaction.atomic():
        # Get or create metadata record
        metadata, created = Metadata.objects.get_or_create(
            fastq_name=fastq_name,
            defaults={
                'organism_common_name': data.get('Organism'),
                'library_prep_method_name': data.get('Library Prep Method'),
                'studies': data.get('Study Set', '')
            }
        )
        if created:
            stats['metadata_created'] += 1
        else:
            # Update existing metadata
            metadata.organism_common_name = data.get('Organism', metadata.organism_common_name)
            metadata.library_prep_method_name = data.get('Library Prep Method', metadata.library_prep_method_name)
            metadata.studies = data.get('Study Set', metadata.studies)
            metadata.save()
            stats['metadata_updated'] += 1
        
        # Get or create main record
        main, created = Main.objects.get_or_create(
            fastq_name=metadata,
            defaults={
                'study_set': data.get('Study Set'),
                'organism': data.get('Organism'),
                'library_prep_method': data.get('Library Prep Method'),
                'alignment_status': data.get('Alignment'),
                'postqc_status': data.get('Post-Alignment'),
                'ingest_status': data.get('Ingest')
            }
        )
        if created:
            stats['main_created'] += 1
        else:
            # Update existing main record
            main.study_set = data.get('Study Set', main.study_set)
            main.organism = data.get('Organism', main.organism)
            main.library_prep_method = data.get('Library Prep Method', main.library_prep_method)
            main.alignment_status = data.get('Alignment', main.alignment_status)
            main.postqc_status = data.get('Post-Alignment', main.postqc_status)
            main.ingest_status = data.get('Ingest', main.ingest_status)
            main.save()
            stats['main_updated'] += 1
        
        # Get or create load association if Load Name exists
        if data.get('Load Name'):
            _, created = LoadAssociation.objects.get_or_create(
                fastq_name=metadata,
                load_name=data['Load Name']
            )
            if created:
                stats['load_association'] += 1
        
        # Get or create alignment record if data exists
        alignment_status = data.get('Alignment')
        if alignment_status:
            _, created = Alignment.objects.get_or_create(
                fastq_name=metadata,
                defaults={
                    'status_id': alignment_status,
                    'start_time': None,
                    'end_time': parse_datetime(data.get('Alignment Time')),
                    'fid': data.get('FID-Alignment', '')
                }
            )
            if created:
                stats['alignment'] += 1
            else:
                # Update existing alignment record
                alignment = Alignment.objects.get(fastq_name=metadata)
                alignment.status_id = alignment_status
                alignment.end_time = parse_datetime(data.get('Alignment Time'))
                alignment.fid = data.get('FID-Alignment', alignment.fid)
                alignment.save()
        
        # Get or create ingest record if data exists
        ingest_status = data.get('Ingest')
        if ingest_status:
            _, created = Ingest.objects.get_or_create(
                fastq_name=metadata,
                defaults={
                    'status_id': ingest_status,
                    'start_time': None,
                    'end_time': parse_datetime(data.get('Ingest Time')),
                    'fid': data.get('FID-Ingest', '')
                }
            )
            if created:
                stats['ingest'] += 1
            else:
                # Update existing ingest record
                ingest = Ingest.objects.get(fastq_name=metadata)
                ingest.status_id = ingest_status
                ingest.end_time = parse_datetime(data.get('Ingest Time'))
                ingest.fid = data.get('FID-Ingest', ingest.fid)
                ingest.save()
        
        # Get or create post-alignment QC record if data exists
        postqc_status = data.get('Post-Alignment')
        if postqc_status:
            _, created = PostQC.objects.get_or_create(
                fastq_name=metadata,
                defaults={
                    'status_id': postqc_status,
                    'start_time': None,
                    'end_time': parse_datetime(data.get('Post Alignment Time')),
                    'fid': data.get('FID-Post-Alignment', '')
                }
            )
            if created:
                stats['postqc'] += 1
            else:
                # Update existing postqc record
                postqc = PostQC.objects.get(fastq_name=metadata)
                postqc.status_id = postqc_status
                postqc.end_time = parse_datetime(data.get('Post Alignment Time'))
                postqc.fid = data.get('FID-Post-Alignment', postqc.fid)
                postqc.save()
        
        stats['processed'] += 1
        if stats['processed'] % 100 == 0 or stats['processed'] < 10:
            logger.info(f"Added/Updated record {stats['processed']}: {fastq_name}")

def main():
    """Main execution function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Import study data from JSON file')
    parser.add_argument('--no-clear', action='store_true', help="Don't clear existing data before import")
    parser.add_argument('--file', type=str, help='Path to JSON file to import')
    parser.add_argument('--dry-run', action='store_true', help='Simulate import without making changes')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Clear existing data unless --no-clear flag is provided
    if not args.no_clear and not args.dry_run:
        logger.warning("Clearing existing data...")
        Metadata.objects.all().delete()
        logger.info("Data cleared.")
    elif args.no_clear:
        logger.info("Skipping data clearing (--no-clear flag provided)")
    
    # Load new data
    logger.info("Loading study data...")
    load_study_data(json_path=args.file, dry_run=args.dry_run)
    logger.info("Done!")

if __name__ == "__main__":
    main() 