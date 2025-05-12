#!/usr/bin/env python
"""
OCS Database - Unified Data Importer

This module provides a consolidated interface for importing data into the OCS database.
It supports multiple data sources and formats, including:
- Vendor CSV files (isilon.csv, nwgc.csv, nygc.csv, sample.csv)
- Study JSON files
- Direct database import

Features:
- Single entry point for all data import operations
- Consistent error handling and logging
- Flexible configuration options
- Support for batch processing and transactions
- Dry run mode for testing

Usage:
    python import_ocs/data_import/ocs_database_importer.py [options]

Options:
    --mode MODE       Import mode (vendor_csv, study_json, direct_db) 
    --source SOURCE   For vendor_csv mode: data source (isilon, nwgc, nygc, sample, all)
    --file FILE       For study_json mode: path to JSON or CSV file
    --batch-size N    Number of records per transaction (default: 100)
    --dry-run         Simulate import without making changes
    --debug           Enable debug logging
"""

import os
import sys
import csv
import argparse
import logging
import json
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import utility functions
from import_ocs.utils.config import (
    DATA_SOURCES, DEFAULT_BATCH_SIZE, get_csv_path, get_study_json_path
)
from import_ocs.utils.db_helpers import setup_django_env, get_db_stats, validate_field, get_db_connection
from import_ocs.utils.file_helpers import validate_file_exists, load_json_data

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Setup Django environment
setup_django_env()

# Now we can import Django models
from django.db import transaction
from viewer.core.models import Metadata, Main, Alignment, Ingest, PostQC, LoadAssociation


class OCSDatabaseImporter:
    """
    Unified class for importing data into the OCS database.
    """
    
    def __init__(self, dry_run=False, batch_size=DEFAULT_BATCH_SIZE, debug=False):
        """
        Initialize the importer.
        
        Args:
            dry_run: Whether to simulate the import without making changes
            batch_size: Number of records to process in a single transaction
            debug: Whether to enable debug logging
        """
        self.dry_run = dry_run
        self.batch_size = batch_size
        
        # Set logging level
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled")
            
        logger.info(f"Initialized OCS Database Importer (dry_run={dry_run}, batch_size={batch_size})")
    
    def import_vendor_csv(self, source='all'):
        """
        Import data from vendor CSV files.
        
        Args:
            source: Which source to import (isilon, nwgc, nygc, sample, all)
            
        Returns:
            Dictionary with import statistics
        """
        logger.info(f"Starting vendor CSV import for source: {source}")
        
        total_stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'errors': 0
        }
        
        if source == 'all':
            sources_to_process = DATA_SOURCES
        else:
            if source not in DATA_SOURCES:
                logger.error(f"Invalid source: {source}. Must be one of {DATA_SOURCES} or 'all'")
                return total_stats
            sources_to_process = [source]
        
        for src in sources_to_process:
            csv_path = get_csv_path(src)
            if validate_file_exists(csv_path):
                stats = self._process_vendor_csv(csv_path, src)
                for key in total_stats:
                    total_stats[key] += stats.get(key, 0)
            else:
                logger.warning(f"Skipping {src} import: {csv_path} does not exist.")
        
        if not self.dry_run:
            logger.info("\nImport completed successfully!")
            logger.info(f"Total records processed: {total_stats['processed']}")
            logger.info(f"Total records created: {total_stats['created']}")
            logger.info(f"Total records updated: {total_stats['updated']}")
            logger.info(f"Total errors: {total_stats['errors']}")
            
            # Get current database stats
            db_stats = get_db_stats()
            logger.info("Records in database:")
            for model, count in db_stats.items():
                logger.info(f"  {model}: {count}")
        else:
            logger.info("\nDry run completed. No changes were made to the database.")
            logger.info(f"Total records that would be processed: {total_stats['processed']}")
        
        return total_stats
    
    def import_study_json(self, file_path=None):
        """
        Import data from a study JSON file.
        
        Args:
            file_path: Path to the JSON file (if None, uses default path)
            
        Returns:
            Dictionary with import statistics
        """
        if file_path is None:
            file_path = get_study_json_path()
        
        logger.info(f"Starting study JSON import from: {file_path}")
        
        # Validate file exists with enhanced error messages
        if not validate_file_exists(file_path):
            logger.error(f"Error: JSON file {file_path} does not exist")
            
            # Provide helpful suggestions for common file locations
            common_locations = [
                os.path.join(project_root, 'import_ocs', 'data', 'study.json'),
                '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
            ]
            
            # Check if any of the common locations exist
            existing_files = [loc for loc in common_locations if os.path.exists(loc)]
            
            if existing_files:
                logger.error("You might be looking for one of these existing files:")
                for existing_file in existing_files:
                    logger.error(f"  - {existing_file}")
                logger.error(f"Try running: python import_ocs/data_import/ocs_database_importer.py --mode study_json --file [FILE_PATH]")
            else:
                logger.error("Please check the file path and try again. The file path should be absolute or relative to the project root.")
            
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
        
        # Load the JSON data
        try:
            study_data = load_json_data(file_path)
        except Exception as e:
            logger.error(f"Error loading JSON data: {e}")
            return {
                'processed': 0,
                'errors': 1
            }
        
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
        
        # Skip database operations in dry run mode
        if self.dry_run:
            for i, (fastq_name, data) in enumerate(study_data.items()):
                stats['processed'] += 1
                if stats['processed'] % 100 == 0 or stats['processed'] < 10:
                    logger.info(f"Would add/update record {stats['processed']}: {fastq_name}")
            
            logger.info(f"Total records that would be processed: {stats['processed']}")
            logger.info("Dry run completed. No changes were made to the database.")
            return stats
        
        # Process records in batches
        total_records = len(study_data)
        logger.info(f"Processing {total_records} records in batches of {self.batch_size}")
        
        # Convert dictionary to list of (key, value) pairs for easier batch processing
        records = list(study_data.items())
        
        # Process in batches
        for i in range(0, len(records), self.batch_size):
            batch = records[i:i+self.batch_size]
            self._process_study_batch(batch, stats)
            
            # Log progress
            logger.info(f"Processed {min(i+self.batch_size, total_records)} of {total_records} records")
        
        logger.info(f"Total records processed: {stats['processed']}")
        
        # Get current database stats
        db_stats = get_db_stats()
        for model, count in db_stats.items():
            logger.info(f"{model} records: {count}")
        
        return stats
    
    def import_direct_db(self, file_path=None):
        """
        Import data directly to the database using SQL (bypassing Django ORM).
        
        Args:
            file_path: Path to the JSON file (if None, uses default path)
            
        Returns:
            Dictionary with import statistics
        """
        if file_path is None:
            file_path = get_study_json_path()
        
        logger.info(f"Starting direct database import from: {file_path}")
        
        # Validate file exists with enhanced error messages
        if not validate_file_exists(file_path):
            logger.error(f"Error: JSON file {file_path} does not exist")
            
            # Provide helpful suggestions for common file locations
            common_locations = [
                os.path.join(project_root, 'import_ocs', 'data', 'study.json'),
                '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
            ]
            
            # Check if any of the common locations exist
            existing_files = [loc for loc in common_locations if os.path.exists(loc)]
            
            if existing_files:
                logger.error("You might be looking for one of these existing files:")
                for existing_file in existing_files:
                    logger.error(f"  - {existing_file}")
                logger.error(f"Try running: python import_ocs/data_import/ocs_database_importer.py --mode direct_db --file [FILE_PATH]")
            else:
                logger.error("Please check the file path and try again. The file path should be absolute or relative to the project root.")
            
            return {
                'processed': 0,
                'success': 0,
                'errors': 1
            }
        
        try:
            # Read the JSON file
            study_data = load_json_data(file_path)
            
            total_records = len(study_data)
            logger.info(f"Loaded {total_records} records from JSON file")
            
            if self.dry_run:
                logger.info("Dry run completed. Would have processed the following records:")
                for i, fastq_name in enumerate(study_data.keys()):
                    if i < 5:  # Show only first 5 records in dry run
                        logger.info(f"  {fastq_name}")
                    if i == 5:
                        logger.info(f"  ... and {len(study_data) - 5} more records")
                return {
                    'processed': total_records,
                    'success': 0,
                    'errors': 0
                }
            
            # Convert dictionary to list of (key, value) pairs for easier batch processing
            records = list(study_data.items())
            
            # Connect to the database
            conn = get_db_connection()
            if not conn:
                logger.error("Failed to connect to the database")
                return {
                    'processed': 0,
                    'success': 0,
                    'errors': 1
                }
            
            success_count = 0
            error_count = 0
            
            try:
                # Process in batches
                for i in range(0, len(records), self.batch_size):
                    batch = records[i:i+self.batch_size]
                    
                    # Process batch in a single transaction
                    with conn:
                        with conn.cursor() as cur:
                            batch_success, batch_errors = self._process_direct_batch(cur, batch)
                            success_count += batch_success
                            error_count += batch_errors
                    
                    # Log progress
                    logger.info(f"Processed {min(i+self.batch_size, total_records)} of {total_records} records (success: {success_count}, errors: {error_count})")
            
            finally:
                conn.close()
            
            logger.info(f"Import completed. Success: {success_count}, Errors: {error_count}")
            
            return {
                'processed': total_records,
                'success': success_count,
                'errors': error_count
            }
            
        except Exception as e:
            logger.error(f"Error during direct database import: {e}")
            return {
                'processed': 0,
                'success': 0,
                'errors': 1
            }
    
    def import_with_metadata(self, file_path=None):
        """
        Update database with new fastq names from study.json and add metadata.
        
        This method processes study.json and for new fastq names (not already in the database),
        fetches complete metadata using the OCS command.
        
        Args:
            file_path: Path to the JSON file (if None, uses default path)
            
        Returns:
            Dictionary with import statistics
        """
        if file_path is None:
            file_path = get_study_json_path()
        
        logger.info(f"Starting database update with OCS metadata for new fastq names from: {file_path}")
        
        # Validate file exists with enhanced error messages
        if not validate_file_exists(file_path):
            logger.error(f"Error: JSON file {file_path} does not exist")
            
            # Provide helpful suggestions for common file locations
            common_locations = [
                os.path.join(project_root, 'import_ocs', 'data', 'study.json'),
                '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
            ]
            
            # Check if any of the common locations exist
            existing_files = [loc for loc in common_locations if os.path.exists(loc)]
            
            if existing_files:
                logger.error("You might be looking for one of these existing files:")
                for existing_file in existing_files:
                    logger.error(f"  - {existing_file}")
                logger.error(f"Try running: python import_ocs/ocs_cli.py update_db --file [FILE_PATH]")
            else:
                logger.error("Please check the file path and try again. The file path should be absolute or relative to the project root.")
            
            return {
                'processed': 0,
                'metadata_fetched': 0,
                'metadata_created': 0,
                'metadata_updated': 0,
                'main_created': 0,
                'main_updated': 0,
                'errors': 0
            }
        
        # Load the JSON data
        try:
            study_data = load_json_data(file_path)
        except Exception as e:
            logger.error(f"Error loading JSON data: {e}")
            return {
                'processed': 0,
                'errors': 1
            }
        
        # Initialize stats
        stats = {
            'processed': 0,
            'metadata_fetched': 0,
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
        
        # Skip database operations in dry run mode
        if self.dry_run:
            for i, (fastq_name, data) in enumerate(study_data.items()):
                stats['processed'] += 1
                logger.info(f"Would check if {fastq_name} exists and fetch metadata if new")
                if stats['processed'] % 100 == 0 or stats['processed'] < 10:
                    logger.info(f"Would add/update record {stats['processed']}: {fastq_name}")
            
            logger.info(f"Total records that would be processed: {stats['processed']}")
            logger.info("Dry run completed. No changes were made to the database.")
            return stats
        
        # Process records in batches
        total_records = len(study_data)
        logger.info(f"Processing {total_records} records")
        
        # Instead of batching, process one by one to check for existing records
        for fastq_name, data in study_data.items():
            stats['processed'] += 1
            
            # Check if this fastq_name already exists in the database
            existing_metadata = Metadata.objects.filter(fastq_name=fastq_name).exists()
            
            if not existing_metadata:
                # New fastq_name, fetch metadata from OCS command
                logger.info(f"New fastq name found: {fastq_name}. Fetching metadata...")
                
                try:
                    # Execute the OCS command to get metadata
                    ocs_cmd = f"source /home/svc_bicore/genomics-cloud-services/gcs-cli/.venv/bin/activate && export AWS_PROFILE=aibs-bicore && ocs fastqs list metadata --fastq-name {fastq_name} --detail --format json"
                    result = subprocess.run(["bash", "-c", ocs_cmd], capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        logger.error(f"Error fetching metadata for {fastq_name}: {result.stderr}")
                        stats['errors'] += 1
                        continue
                    
                    try:
                        metadata_json = json.loads(result.stdout)
                        if not metadata_json or len(metadata_json) == 0:
                            logger.warning(f"No metadata found for {fastq_name}")
                            # Fall back to regular processing with limited data from study.json
                            self._process_study_record(fastq_name, data, stats)
                            continue
                        
                        # Process the first item in the metadata list
                        metadata_item = metadata_json[0]
                        
                        # Create metadata record with enhanced information
                        metadata, created = Metadata.objects.get_or_create(
                            fastq_name=fastq_name,
                            defaults={
                                'organism_common_name': metadata_item.get('organism_common_name', ''),
                                'organism_name': metadata_item.get('organism_name', ''),
                                'library_prep_method_name': metadata_item.get('library_prep_method_name', ''),
                                'studies': '+'.join(metadata_item.get('studies', [])),
                                'alignment_method': metadata_item.get('alignment_method', ''),
                                'amplification_id': metadata_item.get('amplification_id'),
                                'amplification_name': metadata_item.get('amplification_name', ''),
                                'batch_name': metadata_item.get('batch_name', ''),
                                'batch_name_from_vendor': metadata_item.get('batch_name_from_vendor', ''),
                                'cell_capture': metadata_item.get('cell_capture'),
                                'cell_prep_type': metadata_item.get('cell_prep_type', ''),
                                'library_prep_method_id': metadata_item.get('library_prep_method_id'),
                                'library_prep_name': metadata_item.get('library_prep_name', ''),
                                'sample_id': metadata_item.get('sample_id'),
                                'sample_name': '+'.join(metadata_item.get('sample_names', [])),
                                'sample_type': metadata_item.get('sample_type', ''),
                                'sequencing_vendor': metadata_item.get('sequencing_vendor', '')
                            }
                        )
                        
                        if created:
                            stats['metadata_created'] += 1
                            stats['metadata_fetched'] += 1
                            logger.info(f"Created new metadata record for {fastq_name} using OCS metadata")
                            
                            # Create main record with data from both sources
                            main, main_created = Main.objects.get_or_create(
                                fastq_name=metadata,
                                defaults={
                                    'study_set': data.get('Study Set', ''),
                                    'organism': metadata_item.get('organism_name', ''),  # Use metadata from OCS
                                    'library_prep_method': metadata_item.get('library_prep_method_name', ''),
                                    'alignment_status': data.get('Alignment', 'NOT COMPLETED'),
                                    'postqc_status': data.get('Post-Alignment', 'NOT COMPLETED'),
                                    'ingest_status': data.get('Ingest', 'NOT COMPLETED')
                                }
                            )
                            
                            if main_created:
                                stats['main_created'] += 1
                            
                            # Add load association if present
                            if 'load_name' in metadata_item and metadata_item['load_name']:
                                load_association, la_created = LoadAssociation.objects.get_or_create(
                                    fastq_name=metadata,
                                    load_name=metadata_item['load_name']
                                )
                                if la_created:
                                    stats['load_association'] += 1
                        
                        # Continue with processing the status fields from study.json
                        self._process_status_fields(metadata, data, stats)
                        
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON response for {fastq_name}: {result.stdout}")
                        stats['errors'] += 1
                        continue
                        
                except Exception as e:
                    logger.error(f"Error processing metadata for {fastq_name}: {e}")
                    stats['errors'] += 1
                    continue
            else:
                # Existing record, use study.json data for updates
                # But don't update organism in main table
                try:
                    self._process_study_record_no_main_organism(fastq_name, data, stats)
                except Exception as e:
                    logger.error(f"Error processing existing record {fastq_name}: {e}")
                    stats['errors'] += 1
                    continue
            
            # Log progress periodically
            if stats['processed'] % 10 == 0:
                logger.info(f"Processed {stats['processed']} of {total_records} records")
        
        logger.info(f"\nImport completed!")
        logger.info(f"Total records processed: {stats['processed']}")
        logger.info(f"New records with metadata fetched from OCS: {stats['metadata_fetched']}")
        logger.info(f"Metadata records created: {stats['metadata_created']}")
        logger.info(f"Metadata records updated: {stats['metadata_updated']}")
        logger.info(f"Main records created: {stats['main_created']}")
        logger.info(f"Main records updated: {stats['main_updated']}")
        logger.info(f"Load associations created: {stats['load_association']}")
        logger.info(f"Errors: {stats['errors']}")
        
        return stats
    
    def _process_study_record_no_main_organism(self, fastq_name, data, stats):
        """
        Process a study JSON record without updating the organism field in the main table.
        
        Args:
            fastq_name: The fastq name
            data: Dictionary containing the record data
            stats: Dictionary to update with processing statistics
        """
        # Create or update metadata
        try:
            metadata, created = Metadata.objects.get_or_create(
                fastq_name=fastq_name,
                defaults={
                    'organism_common_name': data.get('Organism', ''),
                    'library_prep_method_name': data.get('Library Prep Method', ''),
                    'studies': data.get('Study Set', '')
                }
            )
            
            if created:
                stats['metadata_created'] += 1
            else:
                # Update existing record
                if 'Organism' in data:
                    metadata.organism_common_name = data['Organism']
                if 'Library Prep Method' in data:
                    metadata.library_prep_method_name = data['Library Prep Method']
                if 'Study Set' in data:
                    metadata.studies = data['Study Set']
                metadata.save()
                stats['metadata_updated'] += 1
            
            # Create or update Main record, but don't update organism field
            main, created = Main.objects.get_or_create(
                fastq_name=metadata,
                defaults={
                    'study_set': data.get('Study Set', ''),
                    # Don't use study.json's Organism for main table
                    'library_prep_method': data.get('Library Prep Method', ''),
                    'alignment_status': data.get('Alignment', 'NOT COMPLETED'),
                    'postqc_status': data.get('Post-Alignment', 'NOT COMPLETED'),
                    'ingest_status': data.get('Ingest', 'NOT COMPLETED')
                }
            )
            
            if created:
                stats['main_created'] += 1
            else:
                # Update existing record, but skip organism field
                if 'Study Set' in data:
                    main.study_set = data['Study Set']
                if 'Library Prep Method' in data:
                    main.library_prep_method = data['Library Prep Method']
                
                # Update status fields even if they don't exist in data (treat as empty)
                # Alignment status
                new_status = data.get('Alignment', '') if data.get('Alignment', '') else 'NOT COMPLETED'
                # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
                if new_status == 'COMPLETED':
                    main.alignment_status = 'COMPLETED'
                elif main.alignment_status != 'COMPLETED' and main.alignment_status not in ['IN_PROGRESS', 'FAILED']:
                    main.alignment_status = new_status
                    
                # PostQC status
                new_status = data.get('Post-Alignment', '') if data.get('Post-Alignment', '') else 'NOT COMPLETED'
                # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
                if new_status == 'COMPLETED':
                    main.postqc_status = 'COMPLETED'
                elif main.postqc_status != 'COMPLETED' and main.postqc_status not in ['IN_PROGRESS', 'FAILED']:
                    main.postqc_status = new_status
                    
                # Ingest status
                new_status = data.get('Ingest', '') if data.get('Ingest', '') else 'NOT COMPLETED'
                # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
                if new_status == 'COMPLETED':
                    main.ingest_status = 'COMPLETED'
                elif main.ingest_status != 'COMPLETED' and main.ingest_status not in ['IN_PROGRESS', 'FAILED']:
                    main.ingest_status = new_status
                
                main.save()
                stats['main_updated'] += 1
            
            # Process the status fields
            self._process_status_fields(metadata, data, stats)
            
        except Exception as e:
            logger.error(f"Error processing {fastq_name}: {e}")
            stats['errors'] += 1
            raise
    
    def _process_status_fields(self, metadata, data, stats):
        """
        Process status fields for alignment, postqc, and ingest.
        
        Args:
            metadata: The metadata object
            data: Dictionary containing the record data
            stats: Dictionary to update with processing statistics
        """
        from datetime import datetime
        from django.utils.dateparse import parse_datetime
        
        # Parse time strings from study.json
        ingest_time = None
        if 'Ingest Time' in data and data['Ingest Time']:
            ingest_time = parse_datetime(data['Ingest Time'])
            
        alignment_time = None
        if 'Alignment Time' in data and data['Alignment Time']:
            alignment_time = parse_datetime(data['Alignment Time'])
            
        post_alignment_time = None
        if 'Post Alignment Time' in data and data['Post Alignment Time']:
            post_alignment_time = parse_datetime(data['Post Alignment Time'])
        
        # Create or update Alignment record
        alignment, created = Alignment.objects.get_or_create(
            fastq_name=metadata,
            defaults={
                'status_id': 'NOT COMPLETED',
                'start_time': alignment_time,
                'fid': data.get('FID-Alignment', '')
            }
        )
        if created:
            stats['alignment'] += 1
        else:
            # Update existing record with status even if key doesn't exist
            new_status = data.get('Alignment', '') if data.get('Alignment', '') else 'NOT COMPLETED'
            # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
            if new_status == 'COMPLETED':
                alignment.status_id = 'COMPLETED'
            elif alignment.status_id != 'COMPLETED' and alignment.status_id not in ['IN_PROGRESS', 'FAILED']:
                alignment.status_id = new_status
                
            if alignment_time:
                alignment.start_time = alignment_time
            if 'FID-Alignment' in data and data['FID-Alignment']:
                alignment.fid = data['FID-Alignment']
            alignment.save()
        
        # Create or update PostQC record
        postqc, created = PostQC.objects.get_or_create(
            fastq_name=metadata,
            defaults={
                'status_id': 'NOT COMPLETED',
                'start_time': post_alignment_time,
                'fid': data.get('FID-Post-Alignment', '')
            }
        )
        if created:
            stats['postqc'] += 1
        else:
            # Update existing record with status even if key doesn't exist
            new_status = data.get('Post-Alignment', '') if data.get('Post-Alignment', '') else 'NOT COMPLETED'
            # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
            if new_status == 'COMPLETED':
                postqc.status_id = 'COMPLETED'
            elif postqc.status_id != 'COMPLETED' and postqc.status_id not in ['IN_PROGRESS', 'FAILED']:
                postqc.status_id = new_status
                
            # Update start_time and fid if provided
            if post_alignment_time:
                postqc.start_time = post_alignment_time
            if 'FID-Post-Alignment' in data and data['FID-Post-Alignment']:
                postqc.fid = data['FID-Post-Alignment']
            postqc.save()

        # Create or update Ingest record
        ingest, created = Ingest.objects.get_or_create(
            fastq_name=metadata,
            defaults={
                'status_id': 'NOT COMPLETED',
                'start_time': ingest_time,
                'fid': data.get('FID-Ingest', '')
            }
        )
        if created:
            stats['ingest'] += 1
        else:
            # Update existing record with status even if key doesn't exist
            new_status = data.get('Ingest', '') if data.get('Ingest', '') else 'NOT COMPLETED'
            # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
            if new_status == 'COMPLETED':
                ingest.status_id = 'COMPLETED'
            elif ingest.status_id != 'COMPLETED' and ingest.status_id not in ['IN_PROGRESS', 'FAILED']:
                ingest.status_id = new_status
            
            # Update start_time and fid if provided
            if ingest_time:
                ingest.start_time = ingest_time
            if 'FID-Ingest' in data and data['FID-Ingest']:
                ingest.fid = data['FID-Ingest']
            ingest.save()

        # Add load association if present
        if 'Load Name' in data and data['Load Name']:
            load_association, created = LoadAssociation.objects.get_or_create(
                fastq_name=metadata,
                load_name=data['Load Name']
            )
            if created:
                stats['load_association'] += 1
    
    def _load_csv_data(self, file_path):
        """
        Load data from a CSV file.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            List of dictionaries, where each dictionary represents a row in the CSV
        """
        data = []
        
        try:
            with open(file_path, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    data.append(row)
            
            logger.info(f"Loaded {len(data)} rows from {file_path}")
        except Exception as e:
            logger.error(f"Error loading CSV data from {file_path}: {e}")
        
        return data
    
    def _process_vendor_csv(self, csv_path, source_name):
        """
        Process a vendor CSV file and import its data into the database.
        
        Args:
            csv_path: Path to the CSV file
            source_name: Name of the data source (for logging)
            
        Returns:
            Dictionary with statistics about the import
        """
        logger.info(f"Processing {source_name} data from: {csv_path}")
        if self.dry_run:
            logger.info("DRY RUN MODE - No changes will be made to the database")
        else:
            logger.info(f"Using batch size of {self.batch_size} records per transaction")
        
        stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'errors': 0
        }
        
        try:
            # Load CSV data
            csv_data = self._load_csv_data(csv_path)
            
            # Skip database operations in dry run mode
            if self.dry_run:
                for i, row in enumerate(csv_data):
                    stats['processed'] += 1
                    if stats['processed'] % 100 == 0 or stats['processed'] < 10:
                        logger.info(f"Would process record {stats['processed']}: {row.get('Fastq Name', 'unknown')}")
                return stats
            
            # Process records in batches
            total_records = len(csv_data)
            logger.info(f"Processing {total_records} records in batches of {self.batch_size}")
            
            batch = []
            for row in csv_data:
                batch.append(row)
                
                # Process the batch when it reaches the batch size
                if len(batch) >= self.batch_size:
                    self._process_vendor_batch(batch, stats)
                    batch = []
                    
                    # Log progress
                    logger.info(f"Processed {stats['processed']} of {total_records} records ({stats['created']} created, {stats['updated']} updated)")
            
            # Process any remaining records in the last batch
            if batch:
                self._process_vendor_batch(batch, stats)
        
        except Exception as e:
            logger.error(f"Error processing file {csv_path}: {e}")
            stats['errors'] += 1
        
        return stats
    
    def _process_vendor_batch(self, batch, stats):
        """
        Process a batch of vendor CSV records in a single transaction.
        
        Args:
            batch: List of dictionaries containing the record data
            stats: Dictionary to update with processing statistics
        """
        batch_stats = {
            'created': 0,
            'updated': 0,
            'errors': 0
        }
        
        # Process all records in a single transaction
        with transaction.atomic():
            for row in batch:
                try:
                    self._process_vendor_record(row, batch_stats)
                    stats['processed'] += 1
                    
                except Exception as e:
                    batch_stats['errors'] += 1
                    logger.error(f"Error processing row {stats['processed'] + 1}: {e}")
        
        # Update the main stats with the batch results
        stats['created'] += batch_stats['created']
        stats['updated'] += batch_stats['updated']
        stats['errors'] += batch_stats['errors']
    
    def _process_vendor_record(self, row, stats):
        """
        Process a single vendor CSV record.
        
        Args:
            row: Dictionary containing the record data
            stats: Dictionary to update with processing statistics
        """
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
                # Update status fields if they exist in data
                if 'Alignment' in row:
                    main.alignment_status = row['Alignment'] if row['Alignment'] else 'NOT COMPLETED'
                if 'Post-Alignment' in row:
                    main.postqc_status = row['Post-Alignment'] if row['Post-Alignment'] else 'NOT COMPLETED'
                if 'Ingest' in row:
                    main.ingest_status = row['Ingest'] if row['Ingest'] else 'NOT COMPLETED'
                main.save()
                
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"Error processing {fastq_name}: {e}")
            raise
    
    def _process_study_batch(self, batch, stats):
        """
        Process a batch of study JSON records in a single transaction.
        
        Args:
            batch: List of tuples containing (fastq_name, data)
            stats: Dictionary to update with processing statistics
        """
        # Process all records in a single transaction
        with transaction.atomic():
            for fastq_name, data in batch:
                try:
                    self._process_study_record(fastq_name, data, stats)
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error processing {fastq_name}: {e}")
    
    def _process_study_record(self, fastq_name, data, stats):
        """
        Process a single study JSON record.
        
        Args:
            fastq_name: The fastq name
            data: Dictionary containing the record data
            stats: Dictionary to update with processing statistics
        """
        # Implementation of study record processing
        stats['processed'] += 1
        
        # Create or update metadata
        try:
            metadata, created = Metadata.objects.get_or_create(
                fastq_name=fastq_name,
                defaults={
                    'organism_common_name': data.get('Organism', ''),
                    'library_prep_method_name': data.get('Library Prep Method', ''),
                    'studies': data.get('Study Set', '')
                }
            )
            
            if created:
                stats['metadata_created'] += 1
            else:
                # Update existing record
                if 'Organism' in data:
                    metadata.organism_common_name = data['Organism']
                if 'Library Prep Method' in data:
                    metadata.library_prep_method_name = data['Library Prep Method']
                if 'Study Set' in data:
                    metadata.studies = data['Study Set']
                metadata.save()
                stats['metadata_updated'] += 1
            
            # Create or update Main record
            main, created = Main.objects.get_or_create(
                fastq_name=metadata,
                defaults={
                    'study_set': data.get('Study Set', ''),
                    'organism': data.get('Organism', ''),
                    'library_prep_method': data.get('Library Prep Method', ''),
                    'alignment_status': data.get('Alignment', 'NOT COMPLETED'),
                    'postqc_status': data.get('Post-Alignment', 'NOT COMPLETED'),
                    'ingest_status': data.get('Ingest', 'NOT COMPLETED')
                }
            )
            
            if created:
                stats['main_created'] += 1
            else:
                # Update existing record
                if 'Study Set' in data:
                    main.study_set = data['Study Set']
                if 'Organism' in data:
                    main.organism = data['Organism']
                if 'Library Prep Method' in data:
                    main.library_prep_method = data['Library Prep Method']
                
                # Update status fields even if they don't exist in data (treat as empty)
                # Alignment status
                new_status = data.get('Alignment', '') if data.get('Alignment', '') else 'NOT COMPLETED'
                # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
                if new_status == 'COMPLETED':
                    main.alignment_status = 'COMPLETED'
                elif main.alignment_status != 'COMPLETED' and main.alignment_status not in ['IN_PROGRESS', 'FAILED']:
                    main.alignment_status = new_status
                    
                # PostQC status
                new_status = data.get('Post-Alignment', '') if data.get('Post-Alignment', '') else 'NOT COMPLETED'
                # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
                if new_status == 'COMPLETED':
                    main.postqc_status = 'COMPLETED'
                elif main.postqc_status != 'COMPLETED' and main.postqc_status not in ['IN_PROGRESS', 'FAILED']:
                    main.postqc_status = new_status
                    
                # Ingest status
                new_status = data.get('Ingest', '') if data.get('Ingest', '') else 'NOT COMPLETED'
                # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
                if new_status == 'COMPLETED':
                    main.ingest_status = 'COMPLETED'
                elif main.ingest_status != 'COMPLETED' and main.ingest_status not in ['IN_PROGRESS', 'FAILED']:
                    main.ingest_status = new_status
                
                main.save()
                stats['main_updated'] += 1
            
            # Parse time strings from study.json
            from datetime import datetime
            from django.utils.dateparse import parse_datetime
            
            ingest_time = None
            if 'Ingest Time' in data and data['Ingest Time']:
                ingest_time = parse_datetime(data['Ingest Time'])
                
            alignment_time = None
            if 'Alignment Time' in data and data['Alignment Time']:
                alignment_time = parse_datetime(data['Alignment Time'])
                
            post_alignment_time = None
            if 'Post Alignment Time' in data and data['Post Alignment Time']:
                post_alignment_time = parse_datetime(data['Post Alignment Time'])
            
            # Create or update Alignment record
            alignment, created = Alignment.objects.get_or_create(
                fastq_name=metadata,
                defaults={
                    'status_id': 'NOT COMPLETED',
                    'start_time': alignment_time,  # Import time into start_time instead of end_time
                    'fid': data.get('FID-Alignment', '')  # Import FID
                }
            )
            if created:
                stats['alignment'] += 1
            else:
                # Update existing record with status even if key doesn't exist
                new_status = data.get('Alignment', '') if data.get('Alignment', '') else 'NOT COMPLETED'
                # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
                if new_status == 'COMPLETED':
                    alignment.status_id = 'COMPLETED'
                elif alignment.status_id != 'COMPLETED' and alignment.status_id not in ['IN_PROGRESS', 'FAILED']:
                    alignment.status_id = new_status
                    
                if alignment_time:
                    alignment.start_time = alignment_time  # Update start_time instead of end_time
                if 'FID-Alignment' in data and data['FID-Alignment']:
                    alignment.fid = data['FID-Alignment']
                alignment.save()
            
            # Create or update PostQC record
            postqc, created = PostQC.objects.get_or_create(
                fastq_name=metadata,
                defaults={
                    'status_id': 'NOT COMPLETED',
                    'start_time': post_alignment_time,  # Import time into start_time instead of end_time
                    'fid': data.get('FID-Post-Alignment', '')  # Import FID
                }
            )
            if created:
                stats['postqc'] += 1
            else:
                # Update existing record with status even if key doesn't exist
                new_status = data.get('Post-Alignment', '') if data.get('Post-Alignment', '') else 'NOT COMPLETED'
                # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
                if new_status == 'COMPLETED':
                    postqc.status_id = 'COMPLETED'
                elif postqc.status_id != 'COMPLETED' and postqc.status_id not in ['IN_PROGRESS', 'FAILED']:
                    postqc.status_id = new_status
                    
                # Update start_time and fid if provided
                if post_alignment_time:
                    postqc.start_time = post_alignment_time
                if 'FID-Post-Alignment' in data and data['FID-Post-Alignment']:
                    postqc.fid = data['FID-Post-Alignment']
                postqc.save()

            # Create or update Ingest record
            ingest, created = Ingest.objects.get_or_create(
                fastq_name=metadata,
                defaults={
                    'status_id': 'NOT COMPLETED',
                    'start_time': ingest_time,  # Import time into start_time instead of end_time
                    'fid': data.get('FID-Ingest', '')  # Import FID
                }
            )
            if created:
                stats['ingest'] += 1
            else:
                # Update existing record with status even if key doesn't exist
                new_status = data.get('Ingest', '') if data.get('Ingest', '') else 'NOT COMPLETED'
                # Override with COMPLETED if specified, otherwise only update non-COMPLETED statuses
                if new_status == 'COMPLETED':
                    ingest.status_id = 'COMPLETED'
                elif ingest.status_id != 'COMPLETED' and ingest.status_id not in ['IN_PROGRESS', 'FAILED']:
                    ingest.status_id = new_status
                
                # Update start_time and fid if provided
                if ingest_time:
                    ingest.start_time = ingest_time
                if 'FID-Ingest' in data and data['FID-Ingest']:
                    ingest.fid = data['FID-Ingest']
                ingest.save()

            # Add load association if present
            if 'Load Name' in data and data['Load Name']:
                load_association, created = LoadAssociation.objects.get_or_create(
                    fastq_name=metadata,
                    load_name=data['Load Name']
                )
                if created:
                    stats['load_association'] += 1
        
        except Exception as e:
            logger.error(f"Error processing {fastq_name}: {e}")
            stats['errors'] += 1
            raise
    
    def _process_direct_batch(self, cursor, batch):
        """
        Process a batch of records directly through SQL.
        
        Args:
            cursor: Database cursor
            batch: List of tuples containing (fastq_name, data)
            
        Returns:
            Tuple of (success_count, error_count)
        """
        success_count = 0
        error_count = 0
        
        for fastq_name, data in batch:
            try:
                # Insert into metadata table
                cursor.execute("""
                    INSERT INTO metadata (fastq_name, organism_common_name, library_prep_method_name, studies)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (fastq_name) DO UPDATE
                        SET organism_common_name = EXCLUDED.organism_common_name,
                            library_prep_method_name = EXCLUDED.library_prep_method_name,
                            studies = EXCLUDED.studies
                """, (
                    fastq_name,
                    data.get('Organism'),
                    data.get('Library Prep Method'),
                    [data.get('Study Set')] if data.get('Study Set') else []
                ))

                # For status fields, we need to check if the existing status is COMPLETED
                # to avoid downgrading it.
                
                # Check alignment status
                cursor.execute("""
                    SELECT status_id FROM alignment WHERE fastq_name_id = %s
                """, (fastq_name,))
                
                existing_alignment_status = cursor.fetchone()
                # Use 'NOT COMPLETED' for empty or missing values
                alignment_status = 'NOT COMPLETED'
                if 'Alignment' in data and data['Alignment']:
                    alignment_status = data['Alignment']
                
                # Update if the status is COMPLETED or if the existing status isn't COMPLETED, IN_PROGRESS, or FAILED
                if alignment_status == 'COMPLETED' or not existing_alignment_status or (existing_alignment_status[0] != 'COMPLETED' and existing_alignment_status[0] not in ['IN_PROGRESS', 'FAILED']):
                    # Handle 'NA' or empty string in timestamp
                    alignment_time = data.get('Alignment Time')
                    if alignment_time == 'NA' or alignment_time == '':
                        alignment_time = None
                        
                    cursor.execute("""
                        INSERT INTO alignment (fastq_name_id, status_id, start_time, end_time, fid)
                        VALUES (%s, %s, %s, NULL, %s)
                        ON CONFLICT (fastq_name_id) DO UPDATE
                            SET status_id = EXCLUDED.status_id,
                                start_time = EXCLUDED.start_time,
                                fid = EXCLUDED.fid
                    """, (
                        fastq_name,
                        alignment_status,
                        alignment_time,
                        data.get('FID-Alignment')
                    ))
                elif 'FID-Alignment' in data and data['FID-Alignment']:
                    # For records with COMPLETED, IN_PROGRESS, or FAILED status, only update FID if provided
                    cursor.execute("""
                        UPDATE alignment SET fid = %s WHERE fastq_name_id = %s
                    """, (data['FID-Alignment'], fastq_name))

                # Check postqc status
                cursor.execute("""
                    SELECT status_id FROM postqc WHERE fastq_name_id = %s
                """, (fastq_name,))
                
                existing_postqc_status = cursor.fetchone()
                # Use 'NOT COMPLETED' for empty or missing values
                postqc_status = 'NOT COMPLETED'
                if 'Post-Alignment' in data and data['Post-Alignment']:
                    postqc_status = data['Post-Alignment']
                
                # Update if the status is COMPLETED or if the existing status isn't COMPLETED, IN_PROGRESS, or FAILED
                if postqc_status == 'COMPLETED' or not existing_postqc_status or (existing_postqc_status[0] != 'COMPLETED' and existing_postqc_status[0] not in ['IN_PROGRESS', 'FAILED']):
                    # Handle 'NA' or empty string in timestamp
                    post_alignment_time = data.get('Post Alignment Time')
                    if post_alignment_time == 'NA' or post_alignment_time == '':
                        post_alignment_time = None
                        
                    cursor.execute("""
                        INSERT INTO postqc (fastq_name_id, status_id, start_time, end_time, fid)
                        VALUES (%s, %s, %s, NULL, %s)
                        ON CONFLICT (fastq_name_id) DO UPDATE
                            SET status_id = EXCLUDED.status_id,
                                start_time = EXCLUDED.start_time,
                                fid = EXCLUDED.fid
                    """, (
                        fastq_name,
                        postqc_status,
                        post_alignment_time,
                        data.get('FID-Post-Alignment')
                    ))
                elif 'FID-Post-Alignment' in data and data['FID-Post-Alignment']:
                    # For records with COMPLETED, IN_PROGRESS, or FAILED status, only update FID if provided
                    cursor.execute("""
                        UPDATE postqc SET fid = %s WHERE fastq_name_id = %s
                    """, (data['FID-Post-Alignment'], fastq_name))

                # Check ingest status
                cursor.execute("""
                    SELECT status_id FROM ingest WHERE fastq_name_id = %s
                """, (fastq_name,))
                
                existing_ingest_status = cursor.fetchone()
                # Use 'NOT COMPLETED' for empty or missing values
                ingest_status = 'NOT COMPLETED'
                if 'Ingest' in data and data['Ingest']:
                    ingest_status = data['Ingest']
                
                # Update if the status is COMPLETED or if the existing status isn't COMPLETED, IN_PROGRESS, or FAILED
                if ingest_status == 'COMPLETED' or not existing_ingest_status or (existing_ingest_status[0] != 'COMPLETED' and existing_ingest_status[0] not in ['IN_PROGRESS', 'FAILED']):
                    # Handle 'NA' or empty string in timestamp
                    ingest_time = data.get('Ingest Time')
                    if ingest_time == 'NA' or ingest_time == '':
                        ingest_time = None
                        
                    cursor.execute("""
                        INSERT INTO ingest (fastq_name_id, status_id, start_time, end_time, fid)
                        VALUES (%s, %s, %s, NULL, %s)
                        ON CONFLICT (fastq_name_id) DO UPDATE
                            SET status_id = EXCLUDED.status_id,
                                start_time = EXCLUDED.start_time,
                                fid = EXCLUDED.fid
                    """, (
                        fastq_name,
                        ingest_status,
                        ingest_time,
                        data.get('FID-Ingest')
                    ))
                elif 'FID-Ingest' in data and data['FID-Ingest']:
                    # For records with COMPLETED, IN_PROGRESS, or FAILED status, only update FID if provided
                    cursor.execute("""
                        UPDATE ingest SET fid = %s WHERE fastq_name_id = %s
                    """, (data['FID-Ingest'], fastq_name))

                success_count += 1
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing {fastq_name} via direct SQL: {e}")
        
        return success_count, error_count


def main():
    """Main function for command-line execution."""
    parser = argparse.ArgumentParser(description="OCS Database Importer")
    parser.add_argument('--mode', type=str, choices=['vendor_csv', 'study_json', 'direct_db', 'with_metadata'], default='vendor_csv',
                      help='Import mode (vendor_csv, study_json, direct_db, with_metadata)')
    parser.add_argument('--source', type=str, default='all',
                      help='For vendor_csv mode: Which source to import (isilon, nwgc, nygc, sample, all)')
    parser.add_argument('--file', type=str, default=None,
                      help='For study_json/direct_db/with_metadata mode: Path to JSON or CSV file')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                      help=f'Number of records per transaction (default: {DEFAULT_BATCH_SIZE})')
    parser.add_argument('--dry-run', action='store_true',
                      help='Simulate import without making changes')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Initialize the importer
    importer = OCSDatabaseImporter(
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        debug=args.debug
    )
    
    # Perform the import based on the mode
    try:
        if args.mode == 'vendor_csv':
            importer.import_vendor_csv(args.source)
        elif args.mode == 'study_json':
            importer.import_study_json(args.file)
        elif args.mode == 'direct_db':
            importer.import_direct_db(args.file)
        elif args.mode == 'with_metadata':
            importer.import_with_metadata(args.file)
        else:
            logger.error(f"Invalid mode: {args.mode}")
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        if args.file:
            logger.error(f"Please check that the file exists: {args.file}")
            # Suggest the common location
            common_location = '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
            if os.path.exists(common_location):
                logger.error(f"You might be looking for: {common_location}")
        else:
            logger.error("No file path provided. Use --file to specify the JSON file path.")
    except Exception as e:
        logger.error(f"Error executing command {args.mode}: {e}")
        if args.debug:
            import traceback
            logger.error(traceback.format_exc())


if __name__ == "__main__":
    main() 