#!/usr/bin/env python
"""
OCS Database - Status Verification and Fix Tool

This script verifies and fixes status discrepancies between JSON data and
database records. It compares status values in the database with those in
the JSON file, displays current status counts, and allows the user to fix
any discrepancies interactively.

Features:
    - Analyzes status values in both JSON and database
    - Displays detailed status counts for comparison
    - Interactive prompt for confirming fixes
    - Transaction-based updates to ensure database integrity
    - Detailed reporting of changes made
    - Automatic validation of status values and timestamps

Usage:
    python scripts/data_verification/verify_and_fix_status.py [options]
    
Options:
    --json-path PATH   Path to JSON file to use for verification
    --auto-fix         Automatically fix discrepancies without prompting
    --dry-run          Analyze discrepancies without making changes
    --debug            Enable debug logging

Example:
    python scripts/data_verification/verify_and_fix_status.py
    python scripts/data_verification/verify_and_fix_status.py --auto-fix
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Any, Optional, Tuple

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
from scripts.utilities.db_utils import setup_django_env, parse_datetime
from scripts.utilities.file_utils import load_json_data, validate_file_exists

# Setup Django environment
setup_django_env()

# Now we can import Django models
from django.db import transaction
from django.db.models import Count
from viewer.models import Metadata, Alignment, PostQC, Ingest, Main

def get_status_counts(model, field_name: str) -> List[Dict[str, Any]]:
    """
    Get counts of distinct status values for a model field.
    
    Args:
        model: Django model class
        field_name: Field name to count
        
    Returns:
        List of dictionaries with status values and counts
    """
    return list(model.objects.values(field_name)
                .annotate(count=Count(field_name))
                .order_by(field_name))

def get_json_status_counts(data: Dict[str, Dict[str, Any]], field_key: str) -> Dict[str, int]:
    """
    Count status values in JSON data.
    
    Args:
        data: JSON data dictionary
        field_key: Key for the status field in JSON
        
    Returns:
        Dictionary with status values as keys and counts as values
    """
    counts = {}
    for record in data.values():
        status = record.get(field_key)
        if status not in counts:
            counts[status] = 0
        counts[status] += 1
    return counts

def find_discrepancies(data: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Find status discrepancies between JSON and database.
    
    Args:
        data: JSON data dictionary
        
    Returns:
        Dictionary with status types as keys and lists of discrepant fastq names as values
    """
    discrepancies = {
        'alignment': [],
        'postqc': [],
        'ingest': []
    }
    
    # Get all fastq names from database
    db_fastq_names = set(Metadata.objects.values_list('fastq_name', flat=True))
    
    # Check each fastq in JSON against database
    for fastq_name, record in data.items():
        if fastq_name not in db_fastq_names:
            logger.debug(f"Fastq {fastq_name} not found in database")
            continue
        
        try:
            main_record = Main.objects.get(fastq_name=fastq_name)
            
            # Check alignment status
            json_alignment = record.get('Alignment')
            if json_alignment and main_record.alignment_status != json_alignment:
                discrepancies['alignment'].append(fastq_name)
            
            # Check postQC status
            json_postqc = record.get('Post-Alignment')
            if json_postqc and main_record.postqc_status != json_postqc:
                discrepancies['postqc'].append(fastq_name)
            
            # Check ingest status
            json_ingest = record.get('Ingest')
            if json_ingest and main_record.ingest_status != json_ingest:
                discrepancies['ingest'].append(fastq_name)
                
        except Main.DoesNotExist:
            logger.debug(f"Main record for {fastq_name} not found in database")
            continue
    
    return discrepancies

def fix_discrepancies(data: Dict[str, Dict[str, Any]], 
                      discrepancies: Dict[str, List[str]], 
                      auto_fix: bool = False, 
                      dry_run: bool = False) -> Dict[str, int]:
    """
    Fix status discrepancies between JSON and database.
    
    Args:
        data: JSON data dictionary
        discrepancies: Dictionary with status types as keys and lists of discrepant fastq names as values
        auto_fix: Whether to fix discrepancies without prompting
        dry_run: Whether to simulate fixes without making changes
        
    Returns:
        Dictionary with statistics about the fixes
    """
    stats = {
        'alignment_updated': 0,
        'postqc_updated': 0,
        'ingest_updated': 0,
        'errors': 0
    }
    
    # If dry run, just report what would be fixed
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made to the database")
        logger.info(f"Would fix {len(discrepancies['alignment'])} alignment status discrepancies")
        logger.info(f"Would fix {len(discrepancies['postqc'])} postQC status discrepancies")
        logger.info(f"Would fix {len(discrepancies['ingest'])} ingest status discrepancies")
        return stats
    
    # If not auto-fix and there are discrepancies, ask for confirmation
    total_discrepancies = sum(len(discs) for discs in discrepancies.values())
    if not auto_fix and total_discrepancies > 0:
        answer = input(f"\nFound {total_discrepancies} discrepancies. Fix them? (y/n): ")
        if answer.lower() != 'y':
            logger.info("Fix operation cancelled by user.")
            return stats
    
    # Fix alignment status discrepancies
    for fastq_name in discrepancies['alignment']:
        try:
            metadata = Metadata.objects.get(fastq_name=fastq_name)
            main_record = Main.objects.get(fastq_name=metadata)
            json_data = data[fastq_name]
            json_alignment = json_data.get('Alignment')
            
            if json_alignment:
                with transaction.atomic():
                    # Update Main table
                    old_status = main_record.alignment_status
                    main_record.alignment_status = json_alignment
                    main_record.save(update_fields=['alignment_status'])
                    
                    # Update or create Alignment record
                    Alignment.objects.update_or_create(
                        fastq_name=metadata,
                        defaults={
                            'status_id': json_alignment,
                            'end_time': parse_datetime(json_data.get('Alignment Time')),
                            'fid': json_data.get('FID-Alignment', '')
                        }
                    )
                stats['alignment_updated'] += 1
                logger.info(f"Updated alignment status for {fastq_name}: {old_status} -> {json_alignment}")
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"Error updating alignment status for {fastq_name}: {e}")
    
    # Fix postQC status discrepancies
    for fastq_name in discrepancies['postqc']:
        try:
            metadata = Metadata.objects.get(fastq_name=fastq_name)
            main_record = Main.objects.get(fastq_name=metadata)
            json_data = data[fastq_name]
            json_postqc = json_data.get('Post-Alignment')
            
            if json_postqc:
                with transaction.atomic():
                    # Update Main table
                    old_status = main_record.postqc_status
                    main_record.postqc_status = json_postqc
                    main_record.save(update_fields=['postqc_status'])
                    
                    # Update or create PostQC record
                    PostQC.objects.update_or_create(
                        fastq_name=metadata,
                        defaults={
                            'status_id': json_postqc,
                            'end_time': parse_datetime(json_data.get('Post Alignment Time')),
                            'fid': json_data.get('FID-Post-Alignment', '')
                        }
                    )
                stats['postqc_updated'] += 1
                logger.info(f"Updated postQC status for {fastq_name}: {old_status} -> {json_postqc}")
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"Error updating postQC status for {fastq_name}: {e}")
    
    # Fix ingest status discrepancies
    for fastq_name in discrepancies['ingest']:
        try:
            metadata = Metadata.objects.get(fastq_name=fastq_name)
            main_record = Main.objects.get(fastq_name=metadata)
            json_data = data[fastq_name]
            json_ingest = json_data.get('Ingest')
            
            if json_ingest:
                with transaction.atomic():
                    # Update Main table
                    old_status = main_record.ingest_status
                    main_record.ingest_status = json_ingest
                    main_record.save(update_fields=['ingest_status'])
                    
                    # Update or create Ingest record
                    Ingest.objects.update_or_create(
                        fastq_name=metadata,
                        defaults={
                            'status_id': json_ingest,
                            'end_time': parse_datetime(json_data.get('Ingest Time')),
                            'fid': json_data.get('FID-Ingest', '')
                        }
                    )
                stats['ingest_updated'] += 1
                logger.info(f"Updated ingest status for {fastq_name}: {old_status} -> {json_ingest}")
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"Error updating ingest status for {fastq_name}: {e}")
    
    return stats

def verify_and_fix_status(json_path: Optional[str] = None, 
                         auto_fix: bool = False, 
                         dry_run: bool = False) -> Dict[str, int]:
    """
    Verify and fix status discrepancies between JSON and database.
    
    Args:
        json_path: Path to JSON file (if None, uses default path)
        auto_fix: Whether to fix discrepancies without prompting
        dry_run: Whether to simulate fixes without making changes
        
    Returns:
        Dictionary with statistics about the verification and fixes
    """
    if json_path is None:
        json_path = '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
    
    # Validate file exists
    if not validate_file_exists(json_path):
        logger.error(f"Error: {json_path} does not exist")
        return {'errors': 1}
    
    logger.info(f"Reading study data from {json_path}...")
    
    # Load the JSON data
    try:
        study_data = load_json_data(json_path)
    except Exception as e:
        logger.error(f"Error loading JSON data: {e}")
        return {'errors': 1}
    
    total_records = len(study_data)
    logger.info(f"Found {total_records} records in {os.path.basename(json_path)}")
    
    # Get current status counts in the database
    logger.info("\nCurrent status counts in database:")
    
    # Alignment status counts
    alignment_status_counts = get_status_counts(Main, 'alignment_status')
    for status in alignment_status_counts:
        status_str = status['alignment_status'] or 'NULL'
        logger.info(f"Alignment - {status_str}: {status['count']}")
    
    # PostQC status counts
    postqc_status_counts = get_status_counts(Main, 'postqc_status')
    for status in postqc_status_counts:
        status_str = status['postqc_status'] or 'NULL'
        logger.info(f"PostQC - {status_str}: {status['count']}")
    
    # Ingest status counts
    ingest_status_counts = get_status_counts(Main, 'ingest_status')
    for status in ingest_status_counts:
        status_str = status['ingest_status'] or 'NULL'
        logger.info(f"Ingest - {status_str}: {status['count']}")
    
    # Get status counts from JSON
    logger.info("\nStatus counts in JSON data:")
    
    # Alignment status counts in JSON
    alignment_json_counts = get_json_status_counts(study_data, 'Alignment')
    for status, count in sorted(alignment_json_counts.items(), key=lambda x: str(x[0]) if x[0] is not None else ''):
        status_str = status or 'NULL'
        logger.info(f"Alignment - {status_str}: {count}")
    
    # PostQC status counts in JSON
    postqc_json_counts = get_json_status_counts(study_data, 'Post-Alignment')
    for status, count in sorted(postqc_json_counts.items(), key=lambda x: str(x[0]) if x[0] is not None else ''):
        status_str = status or 'NULL'
        logger.info(f"PostQC - {status_str}: {count}")
    
    # Ingest status counts in JSON
    ingest_json_counts = get_json_status_counts(study_data, 'Ingest')
    for status, count in sorted(ingest_json_counts.items(), key=lambda x: str(x[0]) if x[0] is not None else ''):
        status_str = status or 'NULL'
        logger.info(f"Ingest - {status_str}: {count}")
    
    # Find discrepancies
    logger.info("\nFinding status discrepancies...")
    discrepancies = find_discrepancies(study_data)
    
    # Report discrepancy counts
    total_discrepancies = sum(len(discs) for discs in discrepancies.values())
    logger.info(f"Found {len(discrepancies['alignment'])} alignment status discrepancies")
    logger.info(f"Found {len(discrepancies['postqc'])} postQC status discrepancies")
    logger.info(f"Found {len(discrepancies['ingest'])} ingest status discrepancies")
    logger.info(f"Total: {total_discrepancies} discrepancies")
    
    # Fix discrepancies if needed
    stats = {'errors': 0}
    if total_discrepancies > 0:
        stats = fix_discrepancies(study_data, discrepancies, auto_fix, dry_run)
    
    # Display updated status counts if changes were made
    if sum(stats.values()) > 0 and not dry_run:
        logger.info("\nUpdated status counts in database:")
        
        # Updated alignment status counts
        alignment_status_counts = get_status_counts(Main, 'alignment_status')
        for status in alignment_status_counts:
            status_str = status['alignment_status'] or 'NULL'
            logger.info(f"Alignment - {status_str}: {status['count']}")
        
        # Updated postQC status counts
        postqc_status_counts = get_status_counts(Main, 'postqc_status')
        for status in postqc_status_counts:
            status_str = status['postqc_status'] or 'NULL'
            logger.info(f"PostQC - {status_str}: {status['count']}")
        
        # Updated ingest status counts
        ingest_status_counts = get_status_counts(Main, 'ingest_status')
        for status in ingest_status_counts:
            status_str = status['ingest_status'] or 'NULL'
            logger.info(f"Ingest - {status_str}: {status['count']}")
    
    # Report summary
    if not dry_run:
        logger.info("\nStatus verification and fix completed!")
        if stats.get('alignment_updated', 0) > 0:
            logger.info(f"Fixed {stats['alignment_updated']} alignment status discrepancies")
        if stats.get('postqc_updated', 0) > 0:
            logger.info(f"Fixed {stats['postqc_updated']} postQC status discrepancies")
        if stats.get('ingest_updated', 0) > 0:
            logger.info(f"Fixed {stats['ingest_updated']} ingest status discrepancies")
        if stats.get('errors', 0) > 0:
            logger.warning(f"Encountered {stats['errors']} errors during fixes")
    
    return stats

def main():
    """Main execution function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Verify and fix status discrepancies')
    parser.add_argument('--json-path', type=str, help='Path to JSON file to use for verification')
    parser.add_argument('--auto-fix', action='store_true', help='Automatically fix discrepancies without prompting')
    parser.add_argument('--dry-run', action='store_true', help='Analyze discrepancies without making changes')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Verify and fix status discrepancies
    verify_and_fix_status(
        json_path=args.json_path, 
        auto_fix=args.auto_fix, 
        dry_run=args.dry_run
    )

if __name__ == "__main__":
    main() 