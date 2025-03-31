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