# OCS Database Viewer App

The primary Django application for the OCS Database system. This app provides views, models, and templates for visualizing and managing RNA-Seq sample data.

## Directory Structure

```
viewer/
├── docs/                 # App-specific documentation
├── filters/              # Django filter definitions
├── management/           # Django management commands
├── migrations/           # Database migrations
├── static/               # App-specific static files
│   └── viewer/
│       ├── css/          # Stylesheets
│       └── js/           # JavaScript files
├── tables/               # Django tables2 table definitions
├── templates/            # HTML templates
│   └── viewer/
│       ├── partials/     # Reusable template parts
│       └── pipeline/     # Pipeline-specific templates
├── templatetags/         # Custom template tags
├── tests/                # Test suite
│   ├── fixtures/         # Test data and fixtures
│   ├── integration/      # Integration tests
│   └── unit/             # Unit tests
├── views/                # View functions/classes
├── models.py             # Database models
├── tables.py             # Table definitions
├── urls.py               # URL routing
└── views_root.py         # Root-level views
```

## Models

The app defines the following models:

- **Metadata**: Core sample metadata including fastq_name, organism, and library prep method
- **Alignment**: Sample alignment processing status and metadata
- **PostQC**: Post-alignment QC processing status and metadata
- **Ingest**: Data ingestion processing status and metadata
- **LoadAssociation**: Mapping between fastq names and load names
- **Main**: Combined view of samples with all status fields
- **UserPreferences**: User interface preferences

## Views

- **MainListView**: Primary table view of all samples with filtering
- **PipelineDashboardView**: Pipeline monitoring and control dashboard
- **API Views**: Several API endpoints for metadata access and pipeline operations

## Templates

- **base.html**: Base template with common structure and assets
- **main_list.html**: Primary data table view
- **pipeline/dashboard.html**: Pipeline management dashboard

## Usage

The app provides the following URLs:

- `/`: Main list view of all samples
- `/pipeline/`: Pipeline dashboard for monitoring and controlling sample processing
- `/api/metadata/<fastq_name>/<field_name>/`: API endpoint for accessing specific metadata fields
- `/api/pipeline/submit-alignment/`: API endpoint for submitting alignment jobs
- `/api/pipeline/check-status/`: API endpoint for checking alignment status

## Development

### Adding Models

To add a new model:

1. Define the model in `models.py`
2. Create migrations: `python manage.py makemigrations`
3. Apply migrations: `python manage.py migrate`
4. Update the relevant tables in `tables.py`

### Adding Views

To add a new view:

1. Create the view function/class in an appropriate file in the `views/` directory
2. Add the URL pattern to `urls.py`
3. Create the template in `templates/viewer/`

### Running Tests

```bash
# Run all tests
python manage.py test viewer.tests

# Run specific test categories
python manage.py test viewer.tests.unit
python manage.py test viewer.tests.integration

# Run a specific test case
python manage.py test viewer.tests.unit.test_models
``` 