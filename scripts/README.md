# Scripts Directory

This directory contains various scripts for data management, import, verification, and utility purposes for the OCS Database project.

## Directory Structure

```
scripts/
├── data_import/      # Scripts for importing data into the database
├── data_verification/# Scripts for verifying data integrity
└── utilities/        # Utility scripts for maintenance tasks
└── debug_tools/      # Scripts for debugging and fixing application issues
```

## Data Import Scripts

### `data_import/load_study_data.py`
- **Purpose**: Loads study data from a JSON file into the Django database
- **Description**: Sets up a Django environment, reads a JSON file containing study data, and creates database records for Metadata, Main, LoadAssociation, Alignment, Ingest, and PostQC models.
- **Usage**: `python scripts/data_import/load_study_data.py`

### `data_import/import_json_data.py`
- **Purpose**: Imports data from a JSON file directly into a PostgreSQL database
- **Description**: Establishes a connection to the database, reads study data from a JSON file, and inserts records into multiple tables, with error handling and transaction management.
- **Usage**: `python scripts/data_import/import_json_data.py`

### `data_import/generate.py`
- **Purpose**: Generates an SQL file for database population
- **Description**: Reads study data from a JSON file and converts it into SQL INSERT statements, handling null values and ensuring no conflicts during insertion.
- **Usage**: `python scripts/data_import/generate.py`

## Data Verification Scripts

### `data_verification/compare_timestamps.py`
- **Purpose**: Compares timestamps between JSON data and database records
- **Description**: Normalizes timestamps, extracts study sets, and identifies mismatches between JSON data and database records, providing a verification report.
- **Usage**: `python scripts/data_verification/compare_timestamps.py`

### `data_verification/verify_and_fix_status.py`
- **Purpose**: Verifies and fixes status discrepancies between JSON data and database records
- **Description**: Compares status values in the database with those in the JSON file, displays current status counts, and allows the user to fix any discrepancies.
- **Usage**: `python scripts/data_verification/verify_and_fix_status.py`

## Utility Scripts

### `utilities/fix_data.py`
- **Purpose**: Fixes data issues in the database
- **Description**: Reads records from a JSON file and updates corresponding database records, with functions for parsing timestamps and processing each record.
- **Usage**: `python scripts/utilities/fix_data.py`

## Debug Tools

These scripts help diagnose and fix issues with the application functionality:

### `debug_tools/verify_toggle_html.py`

This script checks the HTML output of the application for proper column classes and toggle functionality. It examines both the main page and debug page for toggle elements, column classes, and JavaScript functions.

Usage:
```bash
python scripts/debug_tools/verify_toggle_html.py
```

### `debug_tools/fix_toggle_columns.py`

This script fixes issues with toggle column functionality by updating the table.html template to properly include column classes in the rendered table cells.

Usage:
```bash
python scripts/debug_tools/fix_toggle_columns.py
```

### `debug_tools/create_debug_page.py`

This script creates a debug page for toggle functionality testing by adding a new view, template, and URL pattern to the Django application. The debug page displays all toggle controls and their corresponding table columns in a simplified layout.

Usage:
```bash
python scripts/debug_tools/create_debug_page.py
```

## Running Scripts

Most scripts require the Django environment to be set up. Make sure you have installed all dependencies from `requirements.txt` and have configured your database settings before running these scripts.

Example:
```bash
# Activate your virtual environment if using one
source venv/bin/activate

# Run a script
python scripts/data_import/load_study_data.py
```

## Maintenance

When creating new scripts, please follow these guidelines:
1. Place them in the appropriate subdirectory based on their purpose
2. Include a header comment explaining what the script does
3. Add proper documentation to this README file
4. Include error handling and logging
5. Follow the existing code style and conventions 