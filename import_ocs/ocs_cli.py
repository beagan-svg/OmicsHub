#!/usr/bin/env python
"""
OCS Database - Command Line Interface

This script provides a user-friendly command line interface for importing data
into the OCS database. It's a simplified wrapper around the functionality provided
by the ocs_database_importer module.

Usage:
    python import_ocs/ocs_cli.py <command> [options]

Commands:
    vendor       Import data from vendor CSV files
    study        Import data from a study JSON file
    direct       Import data directly to the database using SQL
    update_db    Update DB with new fastq names from study.json and add metadata
    collect      Collect data from vendor sources
    all          Run data collection and import

Options:
    --source SOURCE   For vendor command: data source (isilon, nwgc, nygc, sample, all)
    --file FILE       For study/direct/update_db command: path to JSON file
    --batch-size N    Number of records per transaction (default: 100) [not applicable for update_db]
    --dry-run         Simulate import without making changes
    --debug           Enable debug logging

Examples:
    python import_ocs/ocs_cli.py vendor --source isilon
    python import_ocs/ocs_cli.py study --file /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json
    python import_ocs/ocs_cli.py direct --file /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json
    python import_ocs/ocs_cli.py update_db --file /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json
    python import_ocs/ocs_cli.py all --dry-run

For more detailed documentation, see README_database_importer.md
"""

import os
import sys
import subprocess
import argparse
import logging
import traceback

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import the importer module
from import_ocs.data_import.ocs_database_importer import OCSDatabaseImporter
from import_ocs.utils.config import DEFAULT_BATCH_SIZE, get_study_json_path
from import_ocs.utils.file_helpers import validate_file_exists

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def run_vendor_collection(source='all', debug=False):
    """
    Run the vendor data collection script
    
    This function executes the shell scripts that collect vendor data and save 
    it directly to import_ocs/data/csv directory.
    """
    shell_script = os.path.join(project_root, 'import_ocs', 'shell', 'run_vendor_data_collection.sh')
    
    if not os.path.isfile(shell_script):
        logger.error(f"Vendor collection script not found: {shell_script}")
        return False
    
    cmd = [shell_script, '--collect', source]
    if debug:
        cmd.append('--debug')
    
    logger.info(f"Running vendor data collection for source: {source}")
    try:
        result = subprocess.run(cmd, check=True)
        logger.info("Vendor data collection completed successfully")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Vendor data collection failed: {e}")
        return False

def suggest_file_paths(file_type='study'):
    """
    Suggest common file paths for study.json or vendor CSV files
    
    Args:
        file_type: Type of file to suggest paths for ('study' or 'vendor')
    """
    common_locations = []
    
    if file_type == 'study':
        common_locations = [
            os.path.join(project_root, 'import_ocs', 'data', 'study.json'),
            '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
        ]
        logger.error("Common study.json locations:")
    else:
        common_locations = [
            os.path.join(project_root, 'import_ocs', 'data', 'csv')
        ]
        logger.error("Common vendor CSV locations:")
    
    # Check if any of these locations exist
    for loc in common_locations:
        if os.path.exists(loc):
            logger.error(f"  - {loc} (EXISTS)")
        else:
            logger.error(f"  - {loc}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="OCS Database Command Line Interface")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Vendor command
    vendor_parser = subparsers.add_parser('vendor', help='Import data from vendor CSV files')
    vendor_parser.add_argument('--source', type=str, default='all',
                             help='Data source (isilon, nwgc, nygc, sample, all)')
    vendor_parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                             help=f'Number of records per transaction (default: {DEFAULT_BATCH_SIZE})')
    vendor_parser.add_argument('--dry-run', action='store_true',
                             help='Simulate import without making changes')
    vendor_parser.add_argument('--debug', action='store_true',
                             help='Enable debug logging')
    
    # Study command
    study_parser = subparsers.add_parser('study', help='Import data from a study JSON file using Django ORM')
    study_parser.add_argument('--file', type=str, default=None,
                            help='Path to JSON file (default: use project default)')
    study_parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                            help=f'Number of records per transaction (default: {DEFAULT_BATCH_SIZE})')
    study_parser.add_argument('--dry-run', action='store_true',
                            help='Simulate import without making changes')
    study_parser.add_argument('--debug', action='store_true',
                            help='Enable debug logging')
    
    # Direct command
    direct_parser = subparsers.add_parser('direct', help='Import data directly to the database using SQL (faster)')
    direct_parser.add_argument('--file', type=str, default=None,
                             help='Path to JSON file (default: use project default)')
    direct_parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                             help=f'Number of records per transaction (default: {DEFAULT_BATCH_SIZE})')
    direct_parser.add_argument('--dry-run', action='store_true',
                             help='Simulate import without making changes')
    direct_parser.add_argument('--debug', action='store_true',
                             help='Enable debug logging')
    
    # Update DB command
    update_db_parser = subparsers.add_parser('update_db', help='Update DB with new fastq names from study.json and add metadata')
    update_db_parser.add_argument('--file', type=str, 
                               default='/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json',
                               help='Path to JSON file (default: /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json)')
    update_db_parser.add_argument('--dry-run', action='store_true',
                               help='Simulate import without making changes')
    update_db_parser.add_argument('--debug', action='store_true',
                               help='Enable debug logging')
    
    # Collect command
    collect_parser = subparsers.add_parser('collect', help='Collect data from vendor sources')
    collect_parser.add_argument('--source', type=str, default='all',
                              help='Data source (isilon, nwgc, nygc, all)')
    collect_parser.add_argument('--debug', action='store_true',
                              help='Enable debug logging')
    
    # All command
    all_parser = subparsers.add_parser('all', help='Run data collection and import')
    all_parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                          help=f'Number of records per transaction (default: {DEFAULT_BATCH_SIZE})')
    all_parser.add_argument('--dry-run', action='store_true',
                          help='Simulate import without making changes')
    all_parser.add_argument('--debug', action='store_true',
                          help='Enable debug logging')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        logger.info("\nFor more detailed documentation, see README_database_importer.md")
        return
    
    # Set debug logging if requested
    if hasattr(args, 'debug') and args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Process commands
    try:
        if args.command == 'collect':
            run_vendor_collection(args.source, args.debug)
        
        elif args.command == 'vendor':
            importer = OCSDatabaseImporter(
                dry_run=args.dry_run,
                batch_size=args.batch_size,
                debug=args.debug
            )
            result = importer.import_vendor_csv(args.source)
            if not result:
                suggest_file_paths('vendor')
        
        elif args.command == 'study':
            # Validate file exists before proceeding
            if args.file and not validate_file_exists(args.file):
                logger.error(f"Error: JSON file {args.file} does not exist")
                suggest_file_paths('study')
                return
                
            importer = OCSDatabaseImporter(
                dry_run=args.dry_run,
                batch_size=args.batch_size,
                debug=args.debug
            )
            importer.import_study_json(args.file)
        
        elif args.command == 'direct':
            # Validate file exists before proceeding
            if args.file and not validate_file_exists(args.file):
                logger.error(f"Error: JSON file {args.file} does not exist")
                suggest_file_paths('study')
                return
                
            importer = OCSDatabaseImporter(
                dry_run=args.dry_run,
                batch_size=args.batch_size,
                debug=args.debug
            )
            importer.import_direct_db(args.file)
            
        elif args.command == 'update_db':
            # Validate file exists before proceeding
            if args.file and not validate_file_exists(args.file):
                logger.error(f"Error: JSON file {args.file} does not exist")
                suggest_file_paths('study')
                return
                
            importer = OCSDatabaseImporter(
                dry_run=args.dry_run,
                batch_size=DEFAULT_BATCH_SIZE,
                debug=args.debug
            )
            importer.import_with_metadata(args.file)
        
        elif args.command == 'all':
            # First collect data from vendor sources directly into import_ocs/data/csv
            success = run_vendor_collection('all', args.debug)
            if not success:
                logger.warning("Data collection encountered issues, but continuing with import")
            
            # Then import the collected data from import_ocs/data/csv into the database
            importer = OCSDatabaseImporter(
                dry_run=args.dry_run,
                batch_size=args.batch_size,
                debug=args.debug
            )
            importer.import_vendor_csv('all')
            
            # Try to import study data if available
            study_path = get_study_json_path()
            if os.path.exists(study_path):
                logger.info(f"Study JSON file found at {study_path}, importing...")
                importer.import_study_json(study_path)
            else:
                logger.warning(f"Study JSON file not found at default location: {study_path}")
                suggest_file_paths('study')
    
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        if args.command in ['study', 'direct'] and hasattr(args, 'file'):
            suggest_file_paths('study')
        elif args.command == 'vendor':
            suggest_file_paths('vendor')
    
    except Exception as e:
        logger.error(f"Error executing command {args.command}: {e}")
        if hasattr(args, 'debug') and args.debug:
            logger.error(traceback.format_exc())
        else:
            logger.error("Run with --debug for more detailed error information")

if __name__ == "__main__":
    main() 