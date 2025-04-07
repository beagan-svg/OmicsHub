# OCS Database Scripts

This directory contains scripts for managing and operating the OCS database system.

## Directory Structure

```
scripts/
├── data_import/          # Data import scripts
├── data_verification/    # Data verification scripts
├── debug_tools/          # Debugging utilities
├── management/           # Django management commands
├── shell/                # Shell scripts
└── utilities/            # Utility modules
```

## Data Import Scripts

Scripts for importing data into the database.

| Script | Description | Usage |
|--------|-------------|-------|
| `load_study_data.py` | Import study data from JSON | `python scripts/data_import/load_study_data.py [--no-clear] [--file PATH] [--dry-run] [--debug]` |
| `import_vendor_data.py` | Import vendor data from CSV | `python scripts/data_import/import_vendor_data.py [--source SOURCE] [--clear] [--dry-run] [--debug]` |
| `create_sample_csv.py` | Generate sample CSV data | `python scripts/data_import/create_sample_csv.py` |
| `import_json_data.py` | Generic JSON importer | `python scripts/data_import/import_json_data.py [--file PATH] [--model MODEL]` |
| `generate.py` | Generate test data | `python scripts/data_import/generate.py [--count COUNT] [--output PATH]` |

## Data Verification Scripts

Scripts for verifying data integrity and status.

| Script | Description | Usage |
|--------|-------------|-------|
| `verify_and_fix_status.py` | Verify and fix status discrepancies | `python scripts/data_verification/verify_and_fix_status.py [--json-path PATH] [--auto-fix] [--dry-run] [--debug]` |
| `compare_timestamps.py` | Compare timestamps between sources | `python scripts/data_verification/compare_timestamps.py [--source SOURCE]` |

## Shell Scripts

Shell scripts for automating data collection and import.

| Script | Description | Usage |
|--------|-------------|-------|
| `run_vendor_data_collection.sh` | Collect and import vendor data | `./scripts/shell/run_vendor_data_collection.sh [--collect SOURCE] [--import SOURCE] [--all] [--debug] [--skip-venv]` |
| `isilon.sh` | Collect data from Isilon | `./scripts/shell/isilon.sh` |
| `nwgc.sh` | Collect data from NWGC | `./scripts/shell/nwgc.sh` |
| `nygc.sh` | Collect data from NYGC | `./scripts/shell/nygc.sh` |

## Utility Modules

Utility modules for common operations.

| Module | Description |
|--------|-------------|
| `db_utils.py` | Database utility functions |
| `file_utils.py` | File handling utility functions |
| `schema_utils.py` | Database schema utility functions |
| `fix_data.py` | Data cleanup and repair functions |

## Example Workflows

### Complete Vendor Data Import

```bash
# Collect and import all vendor data
./scripts/shell/run_vendor_data_collection.sh --all

# Collect from a specific source
./scripts/shell/run_vendor_data_collection.sh --collect isilon

# Import from a specific source
./scripts/shell/run_vendor_data_collection.sh --import nwgc
```

### Study Data Import

```bash
# Import study data (preserving existing data)
python scripts/data_import/load_study_data.py --no-clear

# Import from a custom JSON file
python scripts/data_import/load_study_data.py --file /path/to/custom.json
```

### Data Verification

```bash
# Verify and fix status discrepancies
python scripts/data_verification/verify_and_fix_status.py

# Automatically fix status discrepancies
python scripts/data_verification/verify_and_fix_status.py --auto-fix

# Simulate fixes without making changes
python scripts/data_verification/verify_and_fix_status.py --dry-run
```

### Schema Management

```python
# Generate schema documentation
from scripts.utilities.schema_utils import document_schema
document_schema()

# Check database constraints
from scripts.utilities.schema_utils import check_constraints
check_constraints()

# Generate entity-relationship diagram
from scripts.utilities.schema_utils import generate_erd
generate_erd()
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