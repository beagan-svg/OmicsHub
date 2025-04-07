#!/usr/bin/env python
"""
OCS Database - Schema Utilities

This module provides utility functions for working with database schemas,
including schema documentation, migration, and validation. The goal is to
make it easier to maintain and evolve the database schema over time.

Functions:
    get_model_fields: Get information about fields in a Django model
    document_schema: Generate documentation for database schema
    check_constraints: Validate database constraints
    generate_migration: Generate a Django migration from model changes
    generate_erd: Generate entity-relationship diagram
"""

import os
import sys
import logging
from typing import Dict, List, Any, Optional
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import utility functions
from scripts.utilities.db_utils import setup_django_env
from scripts.utilities.file_utils import get_project_root, ensure_dir_exists

def get_model_fields(model) -> List[Dict[str, Any]]:
    """
    Get information about fields in a Django model.
    
    Args:
        model: Django model class
        
    Returns:
        List of dictionaries with field information
    """
    fields = []
    
    for field in model._meta.get_fields():
        field_info = {
            'name': field.name,
            'type': field.get_internal_type(),
            'null': getattr(field, 'null', True),
            'blank': getattr(field, 'blank', True),
            'primary_key': getattr(field, 'primary_key', False),
            'unique': getattr(field, 'unique', False),
            'max_length': getattr(field, 'max_length', None),
        }
        
        # Add relationship information if it's a relation field
        if hasattr(field, 'remote_field') and field.remote_field:
            if field.remote_field.model:
                related_model = field.remote_field.model
                field_info['related_model'] = related_model.__name__
                field_info['related_name'] = getattr(field.remote_field, 'related_name', None)
                field_info['on_delete'] = str(getattr(field.remote_field, 'on_delete', None).__name__)
        
        fields.append(field_info)
    
    return fields

def document_schema(output_path: Optional[str] = None) -> str:
    """
    Generate documentation for the database schema.
    
    Args:
        output_path: Path to save the documentation (if None, uses docs/database_schema.md)
        
    Returns:
        Path to the generated documentation file
    """
    # Setup Django environment
    setup_django_env()
    
    # Import Django models
    from viewer.models import Metadata, Alignment, PostQC, Ingest, LoadAssociation, Main
    
    models = [Metadata, Alignment, PostQC, Ingest, LoadAssociation, Main]
    
    # Create output path if not provided
    if output_path is None:
        project_root = get_project_root()
        docs_dir = os.path.join(project_root, 'docs')
        ensure_dir_exists(docs_dir)
        output_path = os.path.join(docs_dir, 'database_schema.md')
    
    # Generate documentation
    with open(output_path, 'w') as f:
        f.write("# OCS Database Schema\n\n")
        f.write("This document describes the database schema for the OCS database.\n\n")
        
        for model in models:
            f.write(f"## {model.__name__}\n\n")
            f.write(f"**Table Name**: `{model._meta.db_table}`\n\n")
            f.write("| Field | Type | Null | Blank | PK | Unique | Max Length | Related Model | Related Name | On Delete |\n")
            f.write("| ----- | ---- | ---- | ----- | -- | ------ | ---------- | ------------- | ------------ | --------- |\n")
            
            fields = get_model_fields(model)
            for field in fields:
                f.write(f"| {field['name']} | {field['type']} | {field['null']} | {field['blank']} | {field['primary_key']} | {field['unique']} | {field['max_length']} | {field.get('related_model', '')} | {field.get('related_name', '')} | {field.get('on_delete', '')} |\n")
            
            f.write("\n")
    
    logger.info(f"Schema documentation generated at {output_path}")
    return output_path

def check_constraints() -> Dict[str, List[str]]:
    """
    Validate database constraints.
    
    Returns:
        Dictionary with constraint types as keys and lists of validation errors as values
    """
    # Setup Django environment
    setup_django_env()
    
    # Import Django models and database validation
    from django.core.exceptions import ValidationError
    from django.db import connection
    from viewer.models import Metadata, Alignment, PostQC, Ingest, LoadAssociation, Main
    
    models = [Metadata, Alignment, PostQC, Ingest, LoadAssociation, Main]
    
    # Initialize results
    results = {
        'foreign_key': [],
        'unique': [],
        'null': [],
        'type': []
    }
    
    # Check foreign key constraints
    logger.info("Checking foreign key constraints...")
    for model in models:
        for field in model._meta.get_fields():
            if hasattr(field, 'remote_field') and field.remote_field:
                if field.remote_field.model:
                    # Check if any records have invalid foreign keys
                    query = f"""
                    SELECT COUNT(*) 
                    FROM {model._meta.db_table} a 
                    LEFT JOIN {field.remote_field.model._meta.db_table} b 
                    ON a.{field.column} = b.{field.remote_field.field.column} 
                    WHERE a.{field.column} IS NOT NULL 
                    AND b.{field.remote_field.field.column} IS NULL
                    """
                    with connection.cursor() as cursor:
                        cursor.execute(query)
                        count = cursor.fetchone()[0]
                        if count > 0:
                            error = f"{count} records in {model.__name__} have invalid {field.name} foreign keys"
                            results['foreign_key'].append(error)
                            logger.warning(error)
    
    # Check unique constraints
    logger.info("Checking unique constraints...")
    for model in models:
        unique_fields = []
        for field in model._meta.get_fields():
            if getattr(field, 'unique', False):
                unique_fields.append(field.name)
        
        for field_name in unique_fields:
            # Check if any duplicate values exist
            query = f"""
            SELECT {field_name}, COUNT(*) 
            FROM {model._meta.db_table} 
            WHERE {field_name} IS NOT NULL 
            GROUP BY {field_name} 
            HAVING COUNT(*) > 1
            """
            with connection.cursor() as cursor:
                cursor.execute(query)
                duplicates = cursor.fetchall()
                if duplicates:
                    for value, count in duplicates:
                        error = f"{count} duplicate values for {model.__name__}.{field_name}: {value}"
                        results['unique'].append(error)
                        logger.warning(error)
    
    # Check null constraints
    logger.info("Checking null constraints...")
    for model in models:
        for field in model._meta.get_fields():
            if hasattr(field, 'null') and not field.null:
                # Check if any records have null values for non-nullable fields
                query = f"""
                SELECT COUNT(*) 
                FROM {model._meta.db_table} 
                WHERE {field.column} IS NULL
                """
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    count = cursor.fetchone()[0]
                    if count > 0:
                        error = f"{count} records in {model.__name__} have NULL values for non-nullable field {field.name}"
                        results['null'].append(error)
                        logger.warning(error)
    
    # Return results
    return results

def generate_migration(app_name: str, name: str) -> str:
    """
    Generate a Django migration from model changes.
    
    Args:
        app_name: Django app name (e.g. 'viewer')
        name: Migration name
        
    Returns:
        Path to the generated migration file
    """
    # Setup Django environment
    setup_django_env()
    
    # Import Django management command
    from django.core.management import call_command
    
    # Generate migration
    logger.info(f"Generating migration {name} for app {app_name}...")
    call_command('makemigrations', app_name, name=name)
    
    # Get migration file path
    app_migrations_dir = os.path.join(get_project_root(), app_name, 'migrations')
    migration_files = [f for f in os.listdir(app_migrations_dir) if f.endswith(f"{name}.py")]
    if migration_files:
        migration_path = os.path.join(app_migrations_dir, migration_files[0])
        logger.info(f"Migration generated at {migration_path}")
        return migration_path
    else:
        logger.warning(f"Could not find generated migration file for {name}")
        return ""

def generate_erd(output_path: Optional[str] = None) -> str:
    """
    Generate entity-relationship diagram.
    
    Args:
        output_path: Path to save the diagram (if None, uses docs/erd.png)
        
    Returns:
        Path to the generated diagram file
    """
    try:
        # Check if django-extensions is installed
        import django_extensions
    except ImportError:
        logger.error("django-extensions is not installed. Install it with 'pip install django-extensions' to use this function.")
        return ""
    
    # Setup Django environment
    setup_django_env()
    
    # Create output path if not provided
    if output_path is None:
        project_root = get_project_root()
        docs_dir = os.path.join(project_root, 'docs')
        ensure_dir_exists(docs_dir)
        output_path = os.path.join(docs_dir, 'erd.png')
    
    # Generate ERD
    logger.info(f"Generating entity-relationship diagram...")
    from django.core.management import call_command
    
    # Make output directory if it doesn't exist
    output_dir = os.path.dirname(output_path)
    ensure_dir_exists(output_dir)
    
    # Generate ERD using django-extensions
    call_command('graph_models', 'viewer', output=output_path)
    
    if os.path.exists(output_path):
        logger.info(f"Entity-relationship diagram generated at {output_path}")
        return output_path
    else:
        logger.warning(f"Could not generate entity-relationship diagram")
        return ""

if __name__ == "__main__":
    # Setup Django environment
    setup_django_env()
    
    # Document schema
    document_schema()
    
    # Check constraints
    check_constraints() 