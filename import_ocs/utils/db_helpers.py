#!/usr/bin/env python
"""
OCS Database - Database Helper Functions

This module contains utility functions for working with the database,
including setting up the Django environment, parsing datetime values,
validating fields, and retrieving database statistics.
"""

import os
import sys
import logging
import django
from datetime import datetime
from typing import Dict, Optional, Any, List, Tuple

# Import from the config module
from import_ocs.utils.config import DB_CONFIG

# Setup logging
logger = logging.getLogger(__name__)

def setup_django_env():
    """
    Set up the Django environment consistently across all scripts.
    
    This ensures that all scripts use the same Django settings and environment.
    """
    # Add the project root directory to the Python path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)
    
    # Set the Django settings module to use the development settings by default
    # This can be overridden by setting the DJANGO_SETTINGS_MODULE environment variable
    if 'DJANGO_SETTINGS_MODULE' not in os.environ:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    
    # Initialize Django
    django.setup()
    
    logger.info(f"Django environment set up with settings: {os.environ.get('DJANGO_SETTINGS_MODULE')}")

def validate_field(model, field_name, value):
    """
    Validate a field value for a model.
    
    Args:
        model: The Django model class
        field_name: The name of the field to validate
        value: The value to validate
        
    Returns:
        The validated value, or None if the value is invalid
    """
    if value is None or value == '':
        return None
    
    try:
        # Try to convert to the appropriate type
        if field_name in ['amplification_id', 'cell_capture', 'library_prep_method_id', 'sample_id']:
            try:
                return int(value)
            except (ValueError, TypeError):
                logger.warning(f"Invalid value for {field_name}: {value}")
                return None
        return value
    except Exception as e:
        logger.warning(f"Error validating {field_name}: {e}")
        return None

def parse_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
    """
    Parse a datetime string with consistent handling of edge cases.
    
    Args:
        datetime_str: Datetime string to parse
        
    Returns:
        Parsed datetime object or None
    """
    if not datetime_str or datetime_str == 'NULL' or datetime_str == 'None':
        return None
    
    try:
        # Try to parse in various formats
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%d'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue
        
        # If none of the formats match, log a warning and return None
        logger.warning(f"Could not parse datetime string: {datetime_str}")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing datetime {datetime_str}: {e}")
        return None

def get_db_stats() -> Dict[str, int]:
    """
    Get statistics about the database.
    
    Returns:
        Dictionary with model names as keys and record counts as values
    """
    # Import here to avoid circular imports
    from django.db import connection
    
    stats = {}
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM metadata")
            stats['Metadata'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM main")
            stats['Main'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM alignment")
            stats['Alignment'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM ingest")
            stats['Ingest'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM postqc")
            stats['PostQC'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM load_association")
            stats['LoadAssociation'] = cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
    
    return stats

def get_db_connection():
    """
    Get a direct database connection (non-Django).
    
    Returns:
        psycopg2 connection object or None if connection fails
    """
    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname=DB_CONFIG['name'],
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        return conn
    except ImportError:
        logger.error("psycopg2 package is required for direct database connections")
        return None
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None 