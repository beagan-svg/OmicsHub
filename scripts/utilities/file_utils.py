#!/usr/bin/env python
"""
OCS Database - File Utilities

This module provides common utility functions for file operations used across 
multiple scripts in the application. The goal is to reduce code duplication 
and standardize file handling, data validation, and error handling.

Functions:
    get_project_root: Get the project root directory
    ensure_dir_exists: Ensure a directory exists
    get_data_dir: Get the data directory path
    validate_file_exists: Validate that a file exists
    load_json_data: Load data from a JSON file with error handling
    load_csv_data: Load data from a CSV file with error handling
    backup_file: Create a backup of a file
"""

import os
import sys
import json
import csv
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def get_project_root() -> str:
    """
    Get the project root directory.
    
    Returns:
        Absolute path to the project root directory
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def ensure_dir_exists(directory: str) -> bool:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory: Directory path to ensure
        
    Returns:
        True if the directory exists or was created, False otherwise
    """
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}")
        return True
    except Exception as e:
        logger.error(f"Error creating directory {directory}: {e}")
        return False

def get_data_dir(subdir: Optional[str] = None) -> str:
    """
    Get the data directory path.
    
    Args:
        subdir: Optional subdirectory within the data directory
        
    Returns:
        Absolute path to the data directory or subdirectory
    """
    project_root = get_project_root()
    data_dir = os.path.join(project_root, 'data')
    
    if subdir:
        data_dir = os.path.join(data_dir, subdir)
    
    # Ensure the directory exists
    ensure_dir_exists(data_dir)
    
    return data_dir

def validate_file_exists(file_path: str, raise_error: bool = False) -> bool:
    """
    Validate that a file exists.
    
    Args:
        file_path: Path to the file to validate
        raise_error: Whether to raise an error if the file doesn't exist
        
    Returns:
        True if the file exists, False otherwise
        
    Raises:
        FileNotFoundError: If raise_error is True and the file doesn't exist
    """
    if not os.path.exists(file_path):
        if raise_error:
            raise FileNotFoundError(f"File not found: {file_path}")
        logger.warning(f"File not found: {file_path}")
        return False
    
    if not os.path.isfile(file_path):
        if raise_error:
            raise ValueError(f"Path is not a file: {file_path}")
        logger.warning(f"Path is not a file: {file_path}")
        return False
    
    return True

def load_json_data(file_path: str) -> Dict[str, Any]:
    """
    Load data from a JSON file with error handling.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dictionary with the JSON data
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    validate_file_exists(file_path, raise_error=True)
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded JSON data from {file_path}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        raise

def load_csv_data(file_path: str) -> List[Dict[str, str]]:
    """
    Load data from a CSV file with error handling.
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        List of dictionaries with the CSV data
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        csv.Error: If the file contains invalid CSV
    """
    validate_file_exists(file_path, raise_error=True)
    
    try:
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            data = list(reader)
        logger.info(f"Loaded CSV data from {file_path}: {len(data)} records")
        return data
    except csv.Error as e:
        logger.error(f"Error reading CSV from {file_path}: {e}")
        raise

def backup_file(file_path: str, backup_dir: Optional[str] = None) -> Optional[str]:
    """
    Create a backup of a file.
    
    Args:
        file_path: Path to the file to backup
        backup_dir: Directory to store the backup (defaults to a 'backups' directory)
        
    Returns:
        Path to the backup file, or None if the backup failed
    """
    validate_file_exists(file_path, raise_error=True)
    
    if not backup_dir:
        project_root = get_project_root()
        backup_dir = os.path.join(project_root, 'backups')
    
    ensure_dir_exists(backup_dir)
    
    # Generate a timestamp for the backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_name = os.path.basename(file_path)
    backup_file_name = f"{os.path.splitext(file_name)[0]}_{timestamp}{os.path.splitext(file_name)[1]}"
    backup_path = os.path.join(backup_dir, backup_file_name)
    
    try:
        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup of {file_path} at {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Error creating backup of {file_path}: {e}")
        return None 