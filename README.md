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
│   └── wsgi.py                    # WSGI configuration
├── viewer/                         # Main application
│   ├── models/                    # Database models
│   │   ├── __init__.py
│   │   ├── metadata.py
│   │   └── main.py
│   ├── views/                     # View logic
│   │   ├── __init__.py
│   │   └── main.py
│   ├── filters/                   # Custom filters
│   │   ├── __init__.py
│   │   └── main.py
│   ├── tables/                    # Table configurations
│   │   ├── __init__.py
│   │   └── main.py
│   ├── templates/                 # HTML templates
│   │   └── viewer/
│   │       ├── base/             # Base templates
│   │       ├── components/       # Reusable components
│   │       └── main_list.html    # Main view template
│   ├── static/                    # Application-specific static files
│   │   └── viewer/
│   │       ├── css/             # Stylesheets
│   │       ├── js/              # JavaScript files
│   │       └── img/             # Images
│   ├── tests/                    # Test files
│   │   ├── __init__.py
│   │   ├── test_study_sets.py
│   │   ├── test_load_name.py
│   │   └── verify_load_associations.py
│   └── management/               # Management commands
│       └── commands/
├── scripts/                      # Utility scripts
│   ├── generate.py              # Data generation scripts
│   ├── import_json_data.py
│   └── compare_timestamps.py
├── sql/                         # SQL files
│   ├── schema_fixed.sql        # Database schema
│   ├── sample.sql              # Sample data
│   ├── study.sql               # Study data
│   └── alter.sql               # Schema alterations
├── static/                      # Project-wide static files
│   ├── css/                    # Global stylesheets
│   ├── js/                     # Global JavaScript
│   └── img/                    # Global images
├── media/                      # User-uploaded files
├── venv/                       # Python virtual environment
├── manage.py                   # Django management script
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
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
   python manage.py runserver 0.0.0.0:8081
   ```

## Features

- View and filter database records
- Search by fastq name and load name
- Filter by study set, organism, and status
- Sortable table columns
- Responsive design

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