# OCS Database Viewer

A Django web application for viewing and managing OCS database records.

## Project Structure

```
database_ocs/
├── database_ocs_project/           # Main Django project directory
│   ├── settings/                   # Project settings
│   │   ├── base.py                # Base settings
│   │   ├── development.py         # Development settings
│   │   └── production.py          # Production settings
│   ├── urls.py                    # Main URL configuration
│   ├── asgi.py                    # ASGI configuration
│   └── wsgi.py                    # WSGI configuration
├── viewer/                         # Main application
│   ├── migrations/                # Database migrations
│   ├── views/                     # View logic
│   │   ├── __init__.py
│   │   ├── main.py                # Main views
│   │   ├── api.py                 # API views
│   │   ├── toggle_views.py        # Toggle functionality
│   │   └── debug_views.py         # Debug views
│   ├── models.py                  # Database models
│   ├── tables.py                  # Table configurations
│   ├── filters/                   # Custom filters
│   ├── templatetags/              # Custom template tags
│   ├── templates/                 # HTML templates
│   │   ├── viewer/               # App-specific templates
│   │   └── django_tables2/       # Custom django-tables2 templates
│   ├── static/                    # Application-specific static files
│   │   └── viewer/
│   │       ├── css/             # Stylesheets
│   │       ├── js/              # JavaScript files
│   │       └── img/             # Images
│   ├── tests/                    # Test files
│   └── management/               # Management commands
│       └── commands/
├── tests/                         # Project-wide tests
│   ├── scripts/                  # Test scripts
│   └── html/                     # Test HTML output
├── data/                         # Data files
│   └── raw/                      # Raw data files
├── scripts/                      # Utility scripts
│   ├── generate.py              # Data generation scripts
│   ├── import_json_data.py      # JSON import script
│   ├── load_study_data.py       # Study data loader
│   ├── fix_data.py              # Data fixing script
│   └── compare_timestamps.py    # Timestamp comparison
├── sql/                         # SQL files
│   ├── schema.sql              # Database schema
│   └── alignment_model.txt     # Alignment model definition
├── static/                      # Project-wide static files
├── staticfiles/                 # Collected static files
├── logs/                        # Log files
├── media/                       # User-uploaded files
├── venv/                        # Python virtual environment
├── manage.py                    # Django management script
├── requirements.txt             # Python dependencies
├── process_batch.sh             # Batch processing script
└── README.md                    # Project documentation
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
   export DJANGO_SETTINGS_MODULE=database_ocs_project.settings.production
   ```

2. Collect static files:
   ```bash
   python manage.py collectstatic
   ```

3. Run with production server:
   ```bash
   gunicorn database_ocs_project.wsgi:application
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

## Import Process

### 1. Set Environment Variables
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
export DJANGO_SETTINGS_MODULE=database_ocs_project.settings.development
```

### 2. Run the Import Script
```bash
python scripts/data_import/load_study_data.py
```

### 3. Verify the Import
```bash
python verify_import.py
```

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

1. Check database settings in `database_ocs_project/settings/development.py`
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