# OCS CLI

The `ocs_cli.py` script provides a user-friendly command-line interface for the OCS database import functionality. It serves as a simplified wrapper around the more complex `ocs_database_importer.py` module.

## Overview

The OCS CLI offers a streamlined interface with specific commands for common data import tasks:

- **vendor**: Import data from vendor CSV files 
- **study**: Import data from study JSON files using Django ORM
- **direct**: Import data directly to the database using raw SQL (faster)
- **collect**: Collect data from vendor sources
- **all**: Run data collection and import in one command

## Usage

### Basic Command Structure

```bash
python import_ocs/ocs_cli.py <command> [options]
```

### Available Commands

#### 1. Vendor Data Import

Import data from vendor CSV files.

```bash
python import_ocs/ocs_cli.py vendor --source SOURCE
```

Options:
- `--source SOURCE`: Specify which source to import (`isilon`, `nwgc`, `nygc`, `sample`, or `all`)
- `--batch-size N`: Number of records per transaction (default: 100)
- `--dry-run`: Simulate import without making changes
- `--debug`: Enable debug logging

Example:
```bash
python import_ocs/ocs_cli.py vendor --source isilon
```

#### 2. Study Data Import (Django ORM)

Import data from a study JSON file using Django ORM.

```bash
python import_ocs/ocs_cli.py study --file FILE_PATH
```

Options:
- `--file PATH`: Path to JSON file (default: uses project default path)
- `--batch-size N`: Number of records per transaction (default: 100)
- `--dry-run`: Simulate import without making changes
- `--debug`: Enable debug logging

Example:
```bash
python import_ocs/ocs_cli.py study --file /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json
```

#### 3. Direct Database Import

Import data from a JSON file directly to the database using raw SQL. This method is typically faster than the study command for large imports.

```bash
python import_ocs/ocs_cli.py direct --file FILE_PATH
```

Options:
- `--file PATH`: Path to JSON file (default: uses project default path)
- `--batch-size N`: Number of records per transaction (default: 100)
- `--dry-run`: Simulate import without making changes
- `--debug`: Enable debug logging

Example:
```bash
python import_ocs/ocs_cli.py direct --file /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json
```

#### 4. Collect Vendor Data

Run shell scripts to collect data from vendor sources.

```bash
python import_ocs/ocs_cli.py collect --source SOURCE
```

Options:
- `--source SOURCE`: Specify which source to collect (`isilon`, `nwgc`, `nygc`, or `all`)
- `--debug`: Enable debug logging

Example:
```bash
python import_ocs/ocs_cli.py collect --source all
```

#### 5. All-in-One Command

Collect vendor data and import it, along with study data if available.

```bash
python import_ocs/ocs_cli.py all [options]
```

Options:
- `--batch-size N`: Number of records per transaction (default: 100)
- `--dry-run`: Simulate import without making changes
- `--debug`: Enable debug logging

Example:
```bash
python import_ocs/ocs_cli.py all --dry-run
```

## Key Features

### Easy Interface

The CLI provides a simpler interface compared to directly using `ocs_database_importer.py`, with commands that map to common use cases.

### Helpful Error Messages

When files aren't found, the CLI will suggest common locations where files might exist.

### All-in-One Processing

The `all` command combines multiple steps (collect data, import vendor data, import study data) into a single command.

## Comparison with Direct Usage

While `ocs_database_importer.py` offers more flexibility with its `--mode` parameter, `ocs_cli.py` provides a more intuitive command-based interface. 

For example, instead of:
```bash
python import_ocs/data_import/ocs_database_importer.py --mode direct_db --file PATH
```

You can use:
```bash
python import_ocs/ocs_cli.py direct --file PATH
```

## Implementation Details

The CLI internally creates instances of the `OCSDatabaseImporter` class to perform the actual import work, adding extra conveniences like:

- File path suggestions
- Enhanced error handling
- Step-by-step workflows (in the "all" command)
- Collection of vendor data through shell scripts

## Common File Locations

Default file locations that the CLI will suggest if a file is not found:
- `/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json` (common study.json location)
- `[project_root]/import_ocs/data/study.json` (default study.json path)
- `[project_root]/import_ocs/data/csv/` (default CSV directory for vendor files)

## When to Use ocs_cli.py vs. ocs_database_importer.py

- Use `ocs_cli.py` for common workflows and when you prefer a command-based interface
- Use `ocs_database_importer.py` directly when you need more control over the import process

## See Also

For more detailed documentation on the database importer functionality, see `README_database_importer.md`. 