# Vendor Data Collection and Import Guide

This guide provides instructions for collecting data from vendor sources (isilon, NWGC, NYGC) and importing it into the database.

## Overview

The process consists of two main steps:
1. **Data Collection**: Run shell scripts to fetch data from the OCS API and generate CSV files.
2. **Data Import**: Import the generated CSV files into the database.

## Prerequisites

1. **OCS CLI Access**
   - Ensure you have access to the OCS CLI tool
   - The genomics-cloud-services environment should be properly configured

2. **Environment Setup**
   - Make sure your virtual environment is activated:
     ```bash
     cd /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs
     source venv/bin/activate
     ```

3. **Required Permissions**
   - You need appropriate AWS permissions (AWS_PROFILE=aibs-bicore)
   - Filesystem access to write to the data directory

## Data Collection Scripts

Three data collection scripts are available:

1. **isilon.sh**
   - Collects metadata from isilon-s3-backup batches
   - Excludes batches with NexteraXT library prep method
   - Outputs data to `isilon.csv`

2. **nwgc.sh**
   - Collects metadata from NWGC batches
   - Excludes batches with NexteraXT library prep method
   - Outputs data to `nwgc.csv`

3. **nygc.sh**
   - Collects metadata from NYGC batches
   - Excludes batches with NexteraXT library prep method
   - Outputs data to `nygc.csv`

Each script extracts the following fields:
- Fastq Name
- Library Prep Method
- Study Set
- Alignment Method
- Amplification ID
- Amplification
- Batch Name
- Batch Name From Vendor
- Cell Capture
- Cell Prep Type
- Library Prep Method ID
- Library Prep Name
- Load Name
- Organism Common Name
- Organism Name
- Sample ID
- Sequencing Vendor

**Note:** The "Organism Name" field from CSV files is mapped to:
- `organism_common_name` in the Metadata model
- `organism` in the Main model

## Automated Collection and Import

A wrapper script `run_vendor_data_collection.sh` is available to automate both data collection and import:

```bash
# Run the wrapper script
./scripts/shell/run_vendor_data_collection.sh --help

# Collect and import all data
./scripts/shell/run_vendor_data_collection.sh --all

# Collect data from a specific source
./scripts/shell/run_vendor_data_collection.sh --collect isilon

# Import data from a specific source
./scripts/shell/run_vendor_data_collection.sh --import nwgc

# Collect and import from a specific source
./scripts/shell/run_vendor_data_collection.sh --collect nygc --import nygc
```

## Manual Process

### 1. Data Collection

To manually run the data collection scripts:

```bash
# Change to the scripts directory
cd /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs/scripts/shell

# Run the isilon script
./isilon.sh

# Run the NWGC script
./nwgc.sh

# Run the NYGC script
./nygc.sh

# Move the generated CSV files to the data directory
mv *.csv ../../data/csv/
```

### 2. Data Import

To manually import the data into the database:

```bash
# Set environment variables
cd /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs
export PYTHONPATH=$PYTHONPATH:$(pwd)
export DJANGO_SETTINGS_MODULE=config.settings.development

# Import all vendor data
python scripts/data_import/import_vendor_data.py --source all

# Import from a specific source without clearing existing data
python scripts/data_import/import_vendor_data.py --source isilon --no-clear

# Test import without making changes to the database
python scripts/data_import/import_vendor_data.py --source nwgc --dry-run
```

## Data Import Options

The import script supports several options:

```
--source SOURCE    Specify which source to import (isilon, nwgc, nygc, all)
--no-clear         Don't clear existing data before import
--dry-run          Simulate import without making changes to the database
```

## Verification

After importing the data, you can verify it was imported correctly:

```bash
# Set environment variables
cd /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs
export PYTHONPATH=$PYTHONPATH:$(pwd)
export DJANGO_SETTINGS_MODULE=config.settings.development

# Run the verification script
python verify_import.py
```

## Troubleshooting

### Common Issues

1. **OCS CLI Access Issues**
   - Ensure the genomics-cloud-services environment is activated
   - Check that AWS_PROFILE is set to aibs-bicore
   - Verify you have the necessary permissions

2. **Missing CSV Files**
   - Check that the data collection scripts ran successfully
   - Verify that the CSV files were moved to the data/csv directory

3. **Database Import Errors**
   - Ensure the Django environment is properly configured
   - Check that the CSV files have the expected headers
   - Verify the database connection settings

4. **Empty Database After Import**
   - Check if the `--no-clear` flag was used if preserving existing data was intended
   - Verify that the CSV files contain data
   - Check for errors during the import process

### Logs

The scripts output detailed logs to the console. For more thorough debugging:

1. Add the `--dry-run` flag to the import script to simulate import without making changes
2. Check the Django logs for database-related errors
3. Examine the CSV files to ensure they contain the expected data

## Data Flow Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   isilon.sh │     │   nwgc.sh   │     │   nygc.sh   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ isilon.csv  │     │  nwgc.csv   │     │  nygc.csv   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────┬───────┴───────────┬───────┘
                   │                   │
                   ▼                   ▼
         ┌────────────────────────────────┐
         │    import_vendor_data.py       │
         └─────────────────┬──────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │    Database     │
                  └─────────────────┘
```

## Testing the Import Process

For testing purposes, you can use the sample CSV generator to create a test file:

```bash
# Generate a sample CSV file
python scripts/data_import/create_sample_csv.py

# Test the import process in dry-run mode
python scripts/data_import/import_vendor_data.py --source sample --dry-run

# Import the sample data
python scripts/data_import/import_vendor_data.py --source sample
```

This generates a CSV file with 10 random records in `data/csv/sample.csv` that can be used to test the import process without needing to run the actual vendor data collection scripts.

## Performance Considerations

- Data collection scripts can take several minutes to run
- The import process uses Django's transaction management for data integrity
- Consider running during off-hours for production systems
- Monitor database performance during large imports

For any issues or questions, please contact the database administrator. 