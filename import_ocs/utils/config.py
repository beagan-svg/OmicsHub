#!/usr/bin/env python
"""
OCS Database - Configuration Module

This module contains centralized configuration settings for the OCS database import system.
"""

import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Path configuration
PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
IMPORT_OCS_DIR = PROJECT_ROOT / "import_ocs"
DATA_DIR = IMPORT_OCS_DIR / "data"  # Data now inside import_ocs directory
CSV_DIR = DATA_DIR / "csv"
JSON_DIR = DATA_DIR / "json"
LOG_DIR = IMPORT_OCS_DIR / "logs"  # Logs also inside import_ocs directory

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
CSV_DIR.mkdir(exist_ok=True)
JSON_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# Default file paths
DEFAULT_STUDY_JSON = JSON_DIR / "study.json"
LEGACY_STUDY_JSON = Path("/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json")

# Database configuration
DB_CONFIG = {
    'name': os.environ.get('DB_NAME', 'prod_ocs'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', ''),
    'password': os.environ.get('DB_PASSWORD', '')
}

# Data sources
DATA_SOURCES = ['isilon', 'nwgc', 'nygc', 'sample']

# Batch processing settings
DEFAULT_BATCH_SIZE = 100

def get_study_json_path():
    """Returns the path to the study.json file, using DEFAULT_STUDY_JSON if it exists, otherwise LEGACY_STUDY_JSON"""
    if DEFAULT_STUDY_JSON.exists():
        return str(DEFAULT_STUDY_JSON)
    elif LEGACY_STUDY_JSON.exists():
        logger.warning(f"Using legacy path for study.json: {LEGACY_STUDY_JSON}")
        logger.warning(f"Consider moving this file to: {DEFAULT_STUDY_JSON}")
        return str(LEGACY_STUDY_JSON)
    return str(DEFAULT_STUDY_JSON)  # Return default even if it doesn't exist

def get_csv_path(source):
    """Returns the path to a source CSV file"""
    return str(CSV_DIR / f"{source}.csv") 