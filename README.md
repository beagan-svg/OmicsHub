# OCS Database Viewer

A Django web application for viewing and managing OCS database records.

## Project Structure

```
database_ocs/
├── config/                    # All configuration files
│   ├── settings/             # Django settings
│   ├── urls.py               # URL configuration
│   ├── wsgi.py               # WSGI configuration
│   └── asgi.py               # ASGI configuration
├── viewer/                    # Main Django app
├── scripts/                   # All scripts
│   ├── shell/                # Shell scripts (*.sh)
│   ├── management/           # Django management commands
│   ├── data_import/          # Data import scripts
│   ├── data_verification/    # Data verification scripts
│   └── debug_tools/          # Debugging utilities
├── static/                    # Static files
├── staticfiles/              # Collected static files
├── media/                    # Media files
├── data/                     # Data files
│   ├── csv/                  # CSV files
│   └── raw/                  # Raw data files
├── tests/                    # Test files
├── logs/                     # Log files
├── sql/                      # SQL files
├── docs/                     # Documentation
│   └── database_schema.md
├── requirements.txt          # Python dependencies
├── environment.yml           # Conda environment
├── Makefile                  # Build commands
├── manage.py                 # Django management script
└── README.md                 # Project documentation
```

## Setup

1. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run migrations:
   ```bash
   python manage.py migrate
   ```

4. Start development server:
   ```bash
   python manage.py runserver 0.0.0.0:8090
   ```

## Features

- View and filter database records
- Search by fastq name and load name
- Filter by study set, organism, and status
- Sortable table columns
- Responsive design
- Column visibility toggle controls
- User preference persistence

## Development

### Running Tests
```bash
python manage.py test viewer
```

### Code Style
This project follows PEP 8 guidelines. To check code style:
```bash
flake8 viewer/
```

### Database Migrations
To create a new migration:
```bash
python manage.py makemigrations
```

To apply migrations:
```bash
python manage.py migrate
```

## Deployment

1. Set environment variables:
   ```bash
   export DJANGO_SETTINGS_MODULE=config.settings.production
   ```

2. Collect static files:
   ```bash
   python manage.py collectstatic
   ```

3. Run with production server:
   ```bash
   gunicorn config.wsgi:application
   ```

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Run tests
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

# Study Data Import Guide

This guide provides instructions for importing study data into the Django database.

## Project Structure

```
database_ocs/                  # Root project directory
├── config/                    # All configuration files
│   ├── settings/             # Django settings
│   ├── urls.py               # URL configuration
│   ├── wsgi.py               # WSGI configuration
│   └── asgi.py               # ASGI configuration
├── viewer/                    # Main Django app
├── scripts/                   # All scripts
│   ├── shell/                # Shell scripts (*.sh)
│   ├── management/           # Django management commands
│   ├── data_import/          # Data import scripts
│   ├── data_verification/    # Data verification scripts
│   └── debug_tools/          # Debugging utilities
├── static/                    # Static files
├── staticfiles/              # Collected static files
├── media/                    # Media files
├── data/                     # Data files
│   ├── csv/                  # CSV files
│   └── raw/                  # Raw data files
├── tests/                    # Test files
├── logs/                     # Log files
├── sql/                      # SQL files
├── docs/                     # Documentation
│   └── database_schema.md
├── requirements.txt          # Python dependencies
├── environment.yml           # Conda environment
├── Makefile                  # Build commands
├── manage.py                 # Django management script
└── README.md                 # Project documentation
```

## Prerequisites

1. Access to the Django project at:
   ```
   /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs
   ```

2. Access to the study.json file at:
   ```
   /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json
   ```

3. Virtual environment setup:
   ```bash
   cd /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs
   source venv/bin/activate
   ```

## Data Import Quick Guide

For importing study data:

```bash
# Set environment variables
export PYTHONPATH=$PYTHONPATH:$(pwd)
export DJANGO_SETTINGS_MODULE=config.settings.development

# Run the import script
python scripts/data_import/load_study_data.py

# Advanced options available:
python scripts/data_import/load_study_data.py --dry-run  # Test without making changes
python scripts/data_import/load_study_data.py --no-clear  # Don't clear existing data
python scripts/data_import/load_study_data.py --file /path/to/custom.json  # Use custom file
```

## Data Import Process

The import process handles the following data types:

1. **Metadata Records**
   - Fastq name
   - Organism common name
   - Library prep method
   - Study set

2. **Main Records**
   - Study set
   - Organism
   - Library prep method
   - Alignment status
   - Post-QC status
   - Ingest status

3. **Load Association Records**
   - Fastq name
   - Load name

4. **Alignment Records**
   - Status ID
   - Start time
   - End time
   - FID

5. **Post-QC Records**
   - Status ID
   - Start time
   - End time
   - FID

6. **Ingest Records**
   - Status ID
   - Start time
   - End time
   - FID

## Expected Results

After successful import, you should see:
- Metadata records: ~11,800
- Main records: ~11,800
- Load association records: ~11,500
- Alignment records: ~11,700
- Post-QC records: ~11,700
- Ingest records: ~11,700

## Recent Updates

- Added support for updating existing records without clearing data
- Improved error handling for duplicate records
- Added dry-run mode for testing imports
- Enhanced data validation during import
- Added support for custom JSON file paths

## Troubleshooting

1. **Duplicate Key Errors**
   - Use `--no-clear` flag to update existing records
   - Check for data consistency in the JSON file

2. **Missing Data**
   - Verify JSON file path and format
   - Check field mappings in the import script

3. **Type Conversion Errors**
   - Ensure date formats are correct
   - Check for invalid status values

For detailed instructions, see [Importing Study Data](docs/importing_study_data.md).

## Verification Script

The verification script (`verify_import.py`) checks:
- Total record counts for each model
- Sample record details including:
  - FASTQ Name
  - Studies
  - Organism Name

## Notes

- The import process clears existing data before importing new records
- The studies field is stored as a plain string, not a list
- All timestamps are properly formatted during import 

## Vendor Data Import

To collect data from vendor sources (isilon, NWGC, NYGC) and import it into the database:

```bash
# Set environment variables
export PYTHONPATH=$PYTHONPATH:$(pwd)
export DJANGO_SETTINGS_MODULE=config.settings.development

# Run the automated collection and import script
./scripts/shell/run_vendor_data_collection.sh --all

# Or collect from a specific source
./scripts/shell/run_vendor_data_collection.sh --collect isilon

# Or import existing CSV files
./scripts/shell/run_vendor_data_collection.sh --import nwgc
```

For testing purposes, you can use the sample data generator:

```bash
# Generate a sample CSV file with test data
python scripts/data_import/create_sample_csv.py

# Import the sample data
python scripts/data_import/import_vendor_data.py --source sample
```

For detailed instructions, see [Vendor Data Import Guide](docs/vendor_data_import.md). 