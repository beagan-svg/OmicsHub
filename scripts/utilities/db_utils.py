#!/usr/bin/env python
"""
OCS Database - Database Utilities

This module provides common utility functions for database operations used across 
multiple scripts in the application. The goal is to reduce code duplication and
standardize database setup, error handling, and data processing.

Functions:
    setup_django_env: Configure Django environment for database access
    parse_datetime: Parse datetime strings with consistent handling
    safe_get_or_create: Safely get or create records with error handling
    get_db_stats: Get statistics about database record counts
    validate_field: Validate field values based on model definitions
"""

import os
import sys
import django
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, Union
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

def setup_django_env(settings_module: str = 'config.settings.development') -> None:
    """
    Set up Django environment for database access.
    
    Args:
        settings_module: Django settings module to use
    """
    # Add the project root directory to the Python path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)
    
    # Set up Django environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
    django.setup()
    
    logger.info(f"Django environment set up with settings: {settings_module}")

def parse_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
    """
    Parse a datetime string with consistent handling of edge cases.
    
    Args:
        datetime_str: Datetime string to parse
        
    Returns:
        Parsed datetime object or None
    """
    if not datetime_str or datetime_str == "NA":
        return None
    
    try:
        # Handle ISO format with Z
        if 'Z' in datetime_str:
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        # Handle standard ISO format
        return datetime.fromisoformat(datetime_str)
    except (ValueError, TypeError) as e:
        logger.warning(f"Error parsing datetime '{datetime_str}': {e}")
        return None

def safe_get_or_create(model, defaults: Dict[str, Any] = None, **kwargs) -> Tuple[Any, bool]:
    """
    Safely get or create a model instance with error handling.
    
    Args:
        model: Django model class
        defaults: Default values for creating a new instance
        **kwargs: Lookup parameters
        
    Returns:
        Tuple of (instance, created)
    """
    try:
        # Handle numeric fields with empty strings
        for field_name, field_value in kwargs.items():
            if field_value == '':
                field = model._meta.get_field(field_name)
                if field.get_internal_type() in ('IntegerField', 'BigIntegerField', 'FloatField'):
                    kwargs[field_name] = None
        
        defaults = defaults or {}
        for field_name, field_value in defaults.items():
            if field_value == '':
                field = model._meta.get_field(field_name)
                if field.get_internal_type() in ('IntegerField', 'BigIntegerField', 'FloatField'):
                    defaults[field_name] = None
        
        return model.objects.get_or_create(defaults=defaults, **kwargs)
    except Exception as e:
        logger.error(f"Error in safe_get_or_create for {model.__name__}: {e}")
        raise

def get_db_stats() -> Dict[str, int]:
    """
    Get statistics about database record counts.
    
    Returns:
        Dictionary with model names as keys and record counts as values
    """
    from viewer.models import Metadata, Main, Alignment, PostQC, Ingest, LoadAssociation
    
    return {
        'metadata': Metadata.objects.count(),
        'main': Main.objects.count(),
        'alignment': Alignment.objects.count(),
        'postqc': PostQC.objects.count(),
        'ingest': Ingest.objects.count(),
        'load_association': LoadAssociation.objects.count()
    }

def validate_field(model, field_name: str, value: Any) -> Union[Any, None]:
    """
    Validate a field value based on model definitions.
    
    Args:
        model: Django model class
        field_name: Field name to validate
        value: Value to validate
        
    Returns:
        Validated value or None
    """
    if value is None or value == '':
        return None
    
    try:
        field = model._meta.get_field(field_name)
        
        # Convert string to integer for numeric fields
        if field.get_internal_type() in ('IntegerField', 'BigIntegerField'):
            try:
                return int(value)
            except (ValueError, TypeError):
                logger.warning(f"Invalid integer value for {field_name}: {value}")
                return None
        
        # Convert string to float for float fields
        if field.get_internal_type() == 'FloatField':
            try:
                return float(value)
            except (ValueError, TypeError):
                logger.warning(f"Invalid float value for {field_name}: {value}")
                return None
        
        # Truncate string fields that are too long
        if field.get_internal_type() == 'CharField' and isinstance(value, str):
            max_length = getattr(field, 'max_length', None)
            if max_length and len(value) > max_length:
                logger.warning(f"Truncating value for {field_name} from {len(value)} to {max_length} characters")
                return value[:max_length]
        
        return value
    except Exception as e:
        logger.error(f"Error validating field {field_name}: {e}")
        return None 