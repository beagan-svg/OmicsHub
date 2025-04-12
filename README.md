# OCS Database Viewer

A Django web application for viewing and managing RNA-Seq sample data in the OCS (Open Commercialized Sequencing) database.

## Table of Contents
- [Project Overview](#project-overview)
- [Project Structure](#project-structure)
- [Setup and Installation](#setup-and-installation)
- [Running the Application](#running-the-application)
- [Features](#features)
- [Scripts](#scripts)
  - [Data Import Scripts](#data-import-scripts)
  - [Data Verification Scripts](#data-verification-scripts)
  - [Pipeline Scripts](#pipeline-scripts)
  - [Shell Scripts](#shell-scripts)
  - [Utility Scripts](#utility-scripts)
- [Development](#development)
  - [CSS Organization](#css-organization)
  - [Static Files](#static-files)
  - [Version Management](#version-management)
  - [Database Management](#database-management)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Project Overview

The OCS Database Viewer is a web application for accessing, viewing, and managing RNA-Seq sample data. It provides an intuitive interface for filtering, searching, and displaying sample information from various studies. The application supports tracking of alignment, post-QC, and ingest processing statuses for samples.

## Project Structure

```
database_ocs/
├── config/                    # Django configuration
│   ├── settings/             # Environment-specific settings
│   ├── urls.py               # URL configuration
│   ├── wsgi.py               # WSGI configuration
│   └── asgi.py               # ASGI configuration
├── viewer/                    # Main Django app
│   ├── views/                # View functions
│   ├── templates/            # HTML templates
│   ├── static/               # App-specific static files
│   │   └── viewer/           # Namespaced static files
│   │       ├── css/          # Organized CSS structure
│   │       │   ├── base/    # Base styles and variables
│   │       │   ├── components/ # Component-specific styles
│   │       │   ├── pages/   # Page-specific styles
│   │       │   └── utils/   # Utility styles
│   │       └── js/           # JavaScript files
│   ├── models.py             # Database models
│   ├── urls.py               # App URL configuration
│   └── tables.py             # Table definitions
├── scripts/                   # Utility scripts
│   ├── data_import/          # Data import scripts
│   ├── data_verification/    # Data verification scripts
│   ├── pipeline/             # Pipeline processing scripts
│   ├── shell/                # Shell scripts
│   └── utilities/            # Utility functions
├── static/                    # Global static files (placeholder)
├── staticfiles/              # Collected static files (production)
├── media/                    # Media files
├── data/                     # Data storage
│   ├── csv/                  # CSV files
│   └── raw/                  # Raw data files
├── backup_files/             # Database backups organized by version
├── docs/                     # Documentation
├── logs/                     # Log files
│   ├── django/              # Django application logs
│   ├── pipeline/            # Pipeline processing logs
│   └── import/              # Data import logs
├── sql/                      # SQL files and database scripts
├── requirements.txt          # Python dependencies
├── environment.yml           # Conda environment
├── version.txt               # Application version
├── Makefile                  # Build commands
├── manage.py                 # Django management script
└── README.md                 # Project documentation
```

## Setup and Installation

### Prerequisites
- Python 3.8+
- pip or conda package manager
- Git

### Installation Steps

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd database_ocs
   ```

2. Create and activate a virtual environment:
   ```bash
   # Using venv
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Or using conda
   conda env create -f environment.yml
   conda activate ocs-database
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up the database:
   ```bash
   python manage.py migrate
   ```

5. Create a superuser (optional):
   ```bash
   python manage.py createsuperuser
   ```

## Running the Application

### Development Server

To run the development server:

```bash
python manage.py runserver 0.0.0.0:8085
```

This will start the server on port 8085, accessible at http://localhost:8085 or from any network interface.

### Using Makefile

The project includes a Makefile with common commands:

```bash
# Run development server
make runserver

# Apply migrations
make migrate

# Create migrations
make migrations

# Collect static files
make collectstatic

# Run tests
make test

# Clean up generated files
make clean

# Create database backup
make backup-db
```

### Environment Variables

For advanced configurations, you can set the following environment variables:

```bash
export DJANGO_SETTINGS_MODULE=config.settings.development  # or production
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

## Features

- **Sample Browser**: View and filter RNA-Seq samples
- **Advanced Filtering**: Filter by study set, organism, library prep method, and processing status
- **Search Functionality**: Search by fastq name and load name
- **Column Management**: Toggle column visibility to customize the view
- **Responsive Design**: Works on desktop and mobile devices
- **User Preference Persistence**: Remembers column visibility settings
- **Pipeline Dashboard**: Monitor and manage sample processing pipelines
- **Data Import**: Import data from various sources including vendor data

## Scripts

The application includes various scripts for data management, verification, and pipeline processing.

### Data Import Scripts

#### 1. Load Study Data
Imports study data from a JSON file into the database.

```bash
python scripts/data_import/load_study_data.py [options]
```
Options:
- `--no-clear`: Don't clear existing data before import
- `--file PATH`: Import from a specific JSON file
- `--dry-run`: Simulate import without making changes
- `--debug`: Enable debug logging

#### 2. Import Vendor Data
Imports vendor data from CSV files.

```bash
python scripts/data_import/import_vendor_data.py --source SOURCE [options]
```
Options:
- `--source SOURCE`: Data source (isilon, nwgc, nygc, all)
- `--no-clear`: Don't clear existing data
- `--debug`: Enable debug logging

#### 3. Run Vendor Data Collection
Shell script to collect and import vendor data.

```bash
./scripts/shell/run_vendor_data_collection.sh [options]
```
Options:
- `--collect SOURCE`: Collect data from source (isilon, nwgc, nygc, all)
- `--import SOURCE`: Import data from source
- `--all`: Collect and import from all sources
- `--debug`: Enable debug mode

### Data Verification Scripts

#### 1. Verify and Fix Status
Verifies and fixes status discrepancies in the database.

```bash
python scripts/data_verification/verify_and_fix_status.py [options]
```
Options:
- `--auto-fix`: Automatically fix discrepancies
- `--dry-run`: Test without making changes
- `--debug`: Enable debug logging

#### 2. Compare Timestamps
Compares timestamps across different status records.

```bash
python scripts/data_verification/compare_timestamps.py [options]
```

### Pipeline Scripts

#### 1. Alignment Script
Submits fastq files for alignment.

```bash
python scripts/pipeline/alignment.py <batch_line> <workflow> <config_file> [fastq_name]
```
Example:
```bash
python scripts/pipeline/alignment.py "MTX-22019_ATX-26019" mtx config/pipeline_config.yaml
```

#### 2. Post-QC Script
Processes samples after alignment.

```bash
python scripts/pipeline/postqc.py <batch_line> <config_file> [fastq_name]
```

#### 3. Process Batch
Processes a batch of samples.

```bash
./process_batch.sh <load_name> <organism> <library_prep_method>
```

### Shell Scripts

#### 1. Run Vendor Data Collection
Automates collection and import of vendor data.

```bash
./scripts/shell/run_vendor_data_collection.sh --all
```

#### 2. Vendor-specific Scripts
Collect data from specific vendors:

```bash
./scripts/shell/isilon.sh
./scripts/shell/nwgc.sh
./scripts/shell/nygc.sh
```

### Utility Scripts

Various utility functions used by other scripts:

- `scripts/utilities/db_utils.py`: Database operations
- `scripts/utilities/file_utils.py`: File handling operations
- `scripts/utilities/schema_utils.py`: Schema management

## Development

### CSS Organization

The CSS is organized into a modular structure:

- `viewer/static/viewer/css/base/`: Base styles and variables
  - `variables.css`: CSS variables for colors, spacing, etc.
  
- `viewer/static/viewer/css/components/`: Component-specific styles
  - `buttons.css`: Button styles
  - `cards.css`: Card component styles
  - `filters.css`: Filter component styles
  - `tables.css`: Table styles
  
- `viewer/static/viewer/css/pages/`: Page-specific styles
  - `main-list.css`: Styles for the main list page
  - `pipeline.css`: Styles for the pipeline dashboard
  
- `viewer/static/viewer/css/utils/`: Utility styles
  - `animations.css`: Animation definitions
  - `responsive.css`: Media queries and responsive utilities

All CSS files are imported in `viewer/static/viewer/css/main.css`, which is included in the base template.

### Static Files

The application follows Django's recommended approach for static files:

1. **App-specific static files**: Each Django app (in this case, the `viewer` app) has its own static files in a subdirectory matching the app name (`viewer/static/viewer/`).

2. **Static files collection**: Django's `collectstatic` command gathers all static files from all apps and places them in the `staticfiles/` directory for production use.

To work with static files:

- During development, place your static files in the app's static directory (`viewer/static/viewer/`).
- When deploying to production, run `python manage.py collectstatic` to collect all static files to the `staticfiles/` directory.
- In templates, reference static files using the `{% static %}` template tag:
  ```html
  {% load static %}
  <link rel="stylesheet" href="{% static 'viewer/css/main.css' %}">
  ```

### Version Management

The application uses semantic versioning (MAJOR.MINOR.PATCH) tracked in `version.txt`.

- Database backups are organized by version number in the `backup_files/` directory
- Each version folder contains backups related to that specific version
- See `backup_files/README.md` for more information on backup procedures

### Database Management

#### Running Migrations
To create and apply migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

#### Creating Backups
To create a database backup:
```bash
make backup-db
```

This will create a backup in the `backup_files/vX.Y.Z/` directory where X.Y.Z is the current version.

## Deployment

1. Set environment variables:
   ```bash
   export DJANGO_SETTINGS_MODULE=config.settings.production
   ```

2. Collect static files:
   ```bash
   python manage.py collectstatic
   ```

3. Run with a production server:
   ```bash
   gunicorn config.wsgi:application
   ```

## Troubleshooting

### Common Issues

1. **Database Connection Issues**
   - Check database settings in `config/settings/`
   - Verify database server is running

2. **Import Script Errors**
   - Verify file paths and permissions
   - Check data format consistency
   - Use `--debug` flag for detailed logging

3. **Missing Dependencies**
   - Ensure virtual environment is active
   - Run `pip install -r requirements.txt`

### Logs

Check the following log files for troubleshooting:
- `logs/django/django.log`: Django application logs
- `logs/import/vendor_data_*.log`: Vendor data import logs
- `logs/pipeline/pipeline_*.log`: Pipeline processing logs

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Run tests
4. Submit a pull request

For more detailed information on specific features, refer to the documentation in the `docs/` directory. 