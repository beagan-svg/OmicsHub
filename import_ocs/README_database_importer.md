# OCS Database Importer

The `ocs_database_importer.py` script serves as a unified tool for importing data into the OCS database from various sources. This consolidated importer supports multiple data import methods, comprehensive error handling, and flexible configuration options.

## Overview

The OCS Database Importer provides three main import modes:
1. **vendor_csv**: Import data from vendor CSV files (isilon, nwgc, nygc, sample)
2. **study_json**: Import data from study JSON files using Django ORM
3. **direct_db**: Import data from JSON files directly to the database using raw SQL

## Installation

No additional installation is required beyond the standard project dependencies. The script is self-contained within the import_ocs package.

## Usage

### Basic Command Structure

```bash
python import_ocs/data_import/ocs_database_importer.py --mode MODE [options]
```

### Available Modes

#### 1. Vendor CSV Import

Import data from vendor CSV files (isilon.csv, nwgc.csv, nygc.csv, sample.csv).

```bash
python import_ocs/data_import/ocs_database_importer.py --mode vendor_csv --source SOURCE
```

Options:
- `--source SOURCE`: Specify which source to import (`isilon`, `nwgc`, `nygc`, `sample`, or `all`)
- `--batch-size N`: Number of records per transaction (default: 100)
- `--dry-run`: Simulate import without making changes
- `--debug`: Enable debug logging

Example:
```bash
# Import data from isilon CSV
python import_ocs/data_import/ocs_database_importer.py --mode vendor_csv --source isilon

# Import data from all vendor sources (dry run)
python import_ocs/data_import/ocs_database_importer.py --mode vendor_csv --source all --dry-run
```

#### 2. Study JSON Import

Import data from a study JSON file using Django ORM.

```bash
python import_ocs/data_import/ocs_database_importer.py --mode study_json --file FILE_PATH
```

Options:
- `--file PATH`: Path to JSON file (if not specified, uses default path)
- `--batch-size N`: Number of records per transaction (default: 100)
- `--dry-run`: Simulate import without making changes
- `--debug`: Enable debug logging

Example:
```bash
# Import from a specific study.json file
python import_ocs/data_import/ocs_database_importer.py --mode study_json --file /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json
```

#### 3. Direct Database Import

Import data from a JSON file directly to the database using raw SQL (bypassing Django ORM).

```bash
python import_ocs/data_import/ocs_database_importer.py --mode direct_db --file FILE_PATH
```

Options:
- `--file PATH`: Path to JSON file (if not specified, uses default path)
- `--batch-size N`: Number of records per transaction (default: 100)
- `--dry-run`: Simulate import without making changes
- `--debug`: Enable debug logging

Example:
```bash
# Import directly to database from a specific study.json file
python import_ocs/data_import/ocs_database_importer.py --mode direct_db --file /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json
```

## Key Features

### Data Integrity Protection

- **Status Preservation**: The importer will never downgrade a status that is already marked as `COMPLETED` in the database, preserving work that has been done.
- **Empty Value Handling**: Empty status values in the input data are automatically set to `NOT COMPLETED`.
- **Transaction Support**: All database operations are performed in transactions to ensure data consistency.

### Error Handling

- **File Path Suggestions**: If a file is not found, the importer suggests common locations where the file might exist.
- **Comprehensive Logging**: Detailed logs are provided for each operation, making it easy to trace issues.
- **Batch Processing**: Data is processed in configurable batches to optimize performance and minimize memory usage.

### Simulation Mode

The `--dry-run` option allows simulating the import process without making any changes to the database. This is useful for testing and validation.

## How It Works

1. **Data Loading**: The importer reads data from the specified source (CSV or JSON).
2. **Validation**: Basic validation is performed on the input data.
3. **Batch Processing**: Data is processed in batches to optimize performance.
4. **Database Operations**:
   - For new records, entries are created in the appropriate tables.
   - For existing records, values are updated following business rules (like preserving COMPLETED statuses).
5. **Transaction Management**: All database operations are performed within transactions to ensure consistency.
6. **Statistics Reporting**: The importer provides detailed statistics about created/updated records and any errors encountered.

## Database Tables

The importer interacts with the following database tables:

- **Metadata**: Core metadata about each fastq file
- **Main**: Main view/table with combined data
- **Alignment**: Information about alignment status and details
- **PostQC**: Information about post-alignment QC status and details
- **Ingest**: Information about ingest status and details
- **LoadAssociation**: Mapping between fastq files and load names

## Common File Locations

Default file locations that the importer will suggest if a file is not found:
- `/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json` (common study.json location)
- `[project_root]/import_ocs/data/study.json` (default study.json path)
- `[project_root]/import_ocs/data/csv/` (default CSV directory for vendor files)

## Troubleshooting

### File Not Found

If you encounter a "file not found" error, check the file path or use one of the suggested common locations.

### Database Connection Issues

Ensure that the database connection environment variables are properly set:
- `DB_NAME` (default: 'prod_ocs')
- `DB_HOST` (default: 'localhost')
- `DB_USER`
- `DB_PASSWORD`

### Error Messages

If you see "Error processing record" messages, enable debug logging (`--debug`) for more detailed information about what went wrong.

## Performance Considerations

- For larger imports, increase the batch size (`--batch-size`) to optimize performance
- The direct_db mode is generally faster than study_json mode for large imports
- Consider using dry run mode first to estimate the time and resources needed for large imports 