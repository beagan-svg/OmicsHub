# Viewer Application Directory Structure

This document provides a comprehensive overview of the viewer application's directory structure, explaining the purpose and functionality of each component.

## Core Application (`core/`)

### `__init__.py`
- **Purpose**: Makes the viewer directory a Python package
- **Functionality**: Initializes the Django application module

### `urls.py`
- **Purpose**: Defines URL routing for the application
- **Functionality**: 
  - Maps URLs to view functions
  - Defines API endpoints
  - Handles URL patterns for different views

### `models.py`
- **Purpose**: Defines database models
- **Functionality**:
  - Contains Django model classes
  - Defines database schema
  - Manages data relationships
  - Handles data validation

### `views_root.py`
- **Purpose**: Root view configuration
- **Functionality**: 
  - Sets up base view configurations
  - Defines common view behaviors

### `tables.py`
- **Purpose**: Defines data table configurations
- **Functionality**:
  - Configures table display
  - Defines column settings
  - Handles table rendering

## Features

### Data Display (`features/data_display/`)
- **Purpose**: Main data viewing and filtering interface
- **Key Files**:
  - `main.py`: Main list view implementation
  - **Functionality**:
    - Data table display
    - Filtering and search
    - Pagination
    - Column configuration

### Pipeline (`features/pipeline/`)
- **Purpose**: Pipeline processing interface
- **Key Files**:
  - `pipeline.py`: Pipeline view implementation
  - **Functionality**:
    - Job submission
    - Pipeline status monitoring
    - Batch processing

### Job Monitoring (`features/job_monitoring/`)
- **Purpose**: Job tracking and status monitoring
- **Key Files**:
  - `job_monitor.py`: Job monitoring implementation
  - **Functionality**:
    - Job status tracking
    - Progress monitoring
    - Error handling

### Failed Jobs (`features/failed_jobs/`)
- **Purpose**: Failed job management
- **Key Files**:
  - `failed_jobs.py`: Failed jobs handling
  - **Functionality**:
    - Failed job listing
    - Error analysis
    - Retry mechanisms

## Supporting Components

### Filters (`filters/`)
- **Purpose**: Data filtering and search functionality
- **Key Files**:
  - `filters.py`: Filter implementations
  - **Functionality**:
    - Search implementation
    - Multi-select filters
    - Advanced filtering

### Template Tags (`templatetags/`)
- **Purpose**: Custom template functionality
- **Key Files**:
  - `viewer_extras.py`: Custom filters and tags
  - **Functionality**:
    - Form handling
    - Pagination
    - URL parameter management
    - Data formatting

### Utilities (`utils/`)
- **Purpose**: Helper functions and utilities
- **Functionality**:
  - Common helper functions
  - Data processing utilities
  - File handling utilities

## Static Files (`static/`)
- **Purpose**: Static assets
- **Subdirectories**:
  - `css/`: Stylesheets
  - `js/`: JavaScript files
  - `images/`: Image assets

## Templates (`templates/`)
- **Purpose**: HTML templates
- **Key Files**:
  - `main_list.html`: Main data display
  - `pipeline_dashboard.html`: Pipeline interface
  - `job_monitor.html`: Job monitoring
  - `failed_jobs.html`: Failed jobs display

## Management Commands (`management/`)
- **Purpose**: Django management commands
- **Key Files**:
  - `update_job_status.py`: Updates job status
  - `fix_timestamps.py`: Fixes timestamp data
  - `rebuild_table_fields.py`: Rebuilds table fields
  - `verify_column_settings.py`: Verifies column configurations
  - `generate_default_columns.py`: Generates default column settings
  - `reset_column_settings.py`: Resets column configurations
  - `fix_studies_format.py`: Fixes study data format
  - `summarize_data.py`: Generates data summaries
  - `verify_study_sets.py`: Verifies study set data
  - `verify_load_associations.py`: Verifies load associations
  - `populate_load_associations.py`: Populates load association data

## Database Migrations (`migrations/`)
- **Purpose**: Database schema management
- **Functionality**:
  - Tracks database schema changes
  - Manages database versioning
  - Handles data migrations

## Documentation (`docs/`)
- **Purpose**: Application documentation
- **Key Files**:
  - `README.md`: Main documentation
  - `directory_structure.md`: This file

## Application Flow

1. **Data Display**:
   - `features/data_display/main.py` handles the main data display
   - Uses `filters/filters.py` for filtering
   - Renders using `templates/main_list.html`

2. **Pipeline Processing**:
   - `features/pipeline/pipeline.py` manages pipeline operations
   - Uses `management/commands/` for job management
   - Renders using `templates/pipeline_dashboard.html`

3. **Job Monitoring**:
   - `features/job_monitoring/job_monitor.py` handles job tracking
   - Uses `management/update_job_status.py` for updates
   - Renders using `templates/job_monitor.html`

4. **Data Management**:
   - `core/models.py` defines data structure
   - `management/commands/` handle data operations
   - `utils/` provides helper functions

## Key Features

1. **Data Display and Filtering**:
   - Tabular data display
   - Advanced filtering capabilities
   - Search functionality
   - Pagination

2. **Pipeline Management**:
   - Job submission
   - Status monitoring
   - Error handling
   - Batch processing

3. **Data Maintenance**:
   - Data verification
   - Format fixing
   - Association management
   - Column configuration

4. **User Interface**:
   - Responsive design
   - Interactive tables
   - Status indicators
   - Error displays

## Dependencies

- Django
- django-tables2
- django-filter
- Bootstrap 5
- jQuery

## Configuration

- Database settings in Django settings
- URL routing in `core/urls.py`
- Template configuration in `templates/`
- Static file configuration in `static/`

## Best Practices

1. **Code Organization**:
   - Clear separation of concerns
   - Modular design
   - Consistent naming conventions

2. **Data Handling**:
   - Proper model relationships
   - Efficient queries
   - Data validation

3. **User Interface**:
   - Responsive design
   - Clear error messages
   - Intuitive navigation

4. **Maintenance**:
   - Regular data verification
   - Automated testing
   - Clear documentation 