#!/usr/bin/env python
"""
OCS Database - File Helper Functions

This module contains utility functions for working with files,
including validation and loading JSON data.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

# Setup logging
logger = logging.getLogger(__name__)

def validate_file_exists(file_path: str) -> bool:
    """
    Validate that a file exists.
    
    Args:
        file_path: Path to the file to validate
        
    Returns:
        True if the file exists, False otherwise
    """
    if not file_path or not isinstance(file_path, str):
        logger.warning("Invalid file path provided")
        return False
    
    if not os.path.isfile(file_path):
        logger.warning(f"File does not exist: {file_path}")
        return False
    
    return True

def load_json_data(file_path: str) -> Dict[str, Any]:
    """
    Load data from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dictionary containing the JSON data
    """
    if not validate_file_exists(file_path):
        return {}
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        logger.info(f"Successfully loaded data from {file_path}")
        logger.info(f"  Records: {len(data)}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error loading JSON data from {file_path}: {e}")
        return {} 