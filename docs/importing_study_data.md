# Importing Data from study.json

This guide provides comprehensive instructions for importing study data from a JSON file into the database. Follow these steps to ensure a successful import process.

## Prerequisites

1. **Database Setup**
   - Ensure PostgreSQL database is running and properly configured
   - Check that database settings are correct in `config/settings/development.py`

2. **File Access**
   - Verify you have access to the study.json file at:
     ```
     /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json
     ```

3. **Environment Setup**
   - Activate the virtual environment:
     ```bash
     cd /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs
     source venv/bin/activate
     ```

## Import Process

### 1. Set Environment Variables

```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
export DJANGO_SETTINGS_MODULE=config.settings.development
```

### 2. Run the Import Script

```bash
python scripts/data_import/load_study_data.py
```

The script performs the following operations:
- Clears existing data from the database (to prevent duplicates)
- Processes each record from study.json
- Creates corresponding entries in the following models:
  - Metadata
  - Main
  - LoadAssociation
  - Alignment
  - PostQC
  - Ingest

### 3. Verify the Import

After the import completes, you can verify the results using:

```bash
python verify_import.py
```

This will show:
- Total record counts for each model
- Sample record from the Metadata table

## Expected Results

After successful import, you should see:
- Approximately 11,817 records processed
- Confirmation messages for each record added
- A summary showing the total counts for each model:
  - Metadata records: ~11,817
  - Main records: ~11,817
  - LoadAssociation records: ~11,521
  - Alignment records: ~11,768
  - PostQC records: ~11,766
  - Ingest records: ~11,768

## Troubleshooting

### Common Issues and Solutions

1. **Missing Module/Import Errors**
   - Ensure PYTHONPATH includes the project root directory
   - Verify the correct settings module is specified

2. **Database Connection Issues**
   - Check database settings in `config/settings/development.py`
   - Ensure PostgreSQL service is running
   - Verify user permissions for database access

3. **JSON File Access Problems**
   - Confirm the file path is correct
   - Check file permissions
   - Verify file isn't corrupted (try `jq . /path/to/study.json` to validate)

4. **Field Format Issues**
   - The `studies` field is stored as a plain string
   - Timestamps are properly formatted during import
   - If you see unexpected field formats, check the `parse_datetime` function in the import script

### Logging and Debugging

The import script outputs progress information to the console. For more detailed logging:

1. Add print statements to the script for debugging
2. Check Django logs for database-related errors
3. Use the `--dry-run` option if available to simulate the import without making changes

## Data Structure

The study.json file contains records with the following key fields:

| Field | Description | Model |
|-------|-------------|-------|
| FASTQ Name | Unique identifier for the record | Metadata |
| Study Set | Associated studies | Metadata, Main |
| Organism | Organism name | Metadata (organism_common_name), Main |
| Library Prep Method | Method used | Metadata, Main |
| Load Name | Name of the load | LoadAssociation |
| Alignment | Alignment status | Main, Alignment |
| Post-Alignment | Post-alignment QC status | Main, PostQC |
| Ingest | Ingest status | Main, Ingest |
| Alignment Time | Timestamp for alignment | Alignment |
| Post Alignment Time | Timestamp for post-alignment | PostQC |
| Ingest Time | Timestamp for ingest | Ingest |
| FID values | Additional identifiers | Various models |

**Note:** The "Organism" field from study.json is mapped to both:
- `organism_common_name` in the Metadata model (primary mapping)
- `organism_name` in the Metadata model (for backwards compatibility)
- `organism` in the Main model

## Advanced Usage

### Custom Import Options

The import script supports several options:

```bash
# Don't clear existing data before import
python scripts/data_import/load_study_data.py --no-clear

# Import from a different JSON file
python scripts/data_import/load_study_data.py --file /path/to/custom/file.json

# Dry run (simulate without making changes)
python scripts/data_import/load_study_data.py --dry-run
```

Note: Check the script's docstring or help text for the most up-to-date options.

### Incremental Updates

If you need to add new records without clearing existing data:

```bash
python scripts/data_import/load_study_data.py --no-clear --file /path/to/new_records.json
```

## Performance Considerations

- The import process uses Django's transaction management for data integrity
- For large JSON files, the import may take several minutes
- Consider running the import during off-hours for production systems
- Monitor database performance during large imports 