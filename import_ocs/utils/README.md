# Utility Scripts for OCS Database Import

This directory contains utility modules that provide common functionality used by the OCS database import system. These modules handle configuration, database operations, and file management to support the main import scripts.

## Overview

The utils directory contains the following modules:

- **config.py**: Central configuration settings
- **db_helpers.py**: Database connection and operation utilities
- **file_helpers.py**: File handling and validation utilities
- **__init__.py**: Package initialization

## Module Details

### config.py

Provides centralized configuration settings for the entire import system.

Key features:
- Path management for data directories, CSV files, and JSON files
- Environment-based database configuration
- Default batch size and data source definitions
- Functions to get standard file paths

Notable functions:
- `get_study_json_path()`: Returns the appropriate study.json path, checking both default and legacy locations
- `get_csv_path(source)`: Returns the path for a specific vendor CSV file

### db_helpers.py

Handles database connections, validation, and operations.

Key features:
- Django environment setup
- Field validation for database models
- Date/time parsing with consistent handling of edge cases
- Database statistics gathering
- Direct database connection utilities 

Notable functions:
- `setup_django_env()`: Sets up the Django environment consistently across all scripts
- `validate_field(model, field_name, value)`: Validates field values for database models
- `parse_datetime(datetime_str)`: Parses datetime strings with consistent handling of edge cases
- `get_db_stats()`: Returns record counts for all relevant database tables
- `get_db_connection()`: Creates a direct database connection using psycopg2

### file_helpers.py

Provides utilities for file operations and validation.

Key features:
- File existence validation
- JSON data loading with comprehensive error handling
- Logging for file operations

Notable functions:
- `validate_file_exists(file_path)`: Checks if a file exists and logs appropriate warnings
- `load_json_data(file_path)`: Loads data from a JSON file with error handling

## Usage Examples

### Setting Up Django Environment

```python
from import_ocs.utils.db_helpers import setup_django_env

# Set up Django environment before importing Django models
setup_django_env()

# Now we can import Django models
from viewer.core.models import Metadata, Main
```

### Loading JSON Data

```python
from import_ocs.utils.file_helpers import load_json_data
from import_ocs.utils.config import get_study_json_path

# Get the path to the study.json file
file_path = get_study_json_path()

# Load the JSON data
data = load_json_data(file_path)
```

### Accessing Configuration

```python
from import_ocs.utils.config import DATA_SOURCES, DEFAULT_BATCH_SIZE

# Use the defined data sources
for source in DATA_SOURCES:
    print(f"Processing source: {source}")

# Use the default batch size
batch_size = DEFAULT_BATCH_SIZE
```

### Database Operations

```python
from import_ocs.utils.db_helpers import get_db_connection, get_db_stats

# Get database statistics
stats = get_db_stats()
print(f"Records in Metadata table: {stats['Metadata']}")

# Get a direct database connection
conn = get_db_connection()
with conn.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM metadata")
    count = cursor.fetchone()[0]
    print(f"Metadata count: {count}")
```

## Integration

These utility modules are used by:

- **ocs_database_importer.py**: The main database import script
- **ocs_cli.py**: The command-line interface wrapper

By centralizing common functionality in these modules, the main scripts can focus on their specific responsibilities while reusing shared logic for configuration, database operations, and file handling.

## Maintenance

When updating these utility modules, be aware that they are used by multiple scripts. Make sure your changes are backward compatible or update all dependent scripts accordingly.

To test changes to these modules, you can use the main scripts with the `--dry-run` option to ensure they still function correctly. 