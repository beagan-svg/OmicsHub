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
│   └── csv/                  # CSV files
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
│   └── csv/                  # CSV files
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

For detailed instructions, see [Importing Study Data](docs/importing_study_data.md).

## Expected Results

After successful import, you should see:
- Approximately 11,817 records processed
- Confirmation messages for each record added
- A summary showing the total counts for each model:
  - Metadata records: 11,817
  - Main records: 11,817
  - LoadAssociation records: ~11,521
  - Alignment records: ~11,768
  - PostQC records: ~11,766
  - Ingest records: ~11,768

## Troubleshooting

If you encounter any issues:

1. Check database settings in `config/settings/development.py`
2. Verify the study.json file exists and is readable
3. Ensure all required packages are installed in your virtual environment
4. Check Django logs for error messages

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