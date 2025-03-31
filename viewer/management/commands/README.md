# Column Management Utilities

This directory contains management commands for working with column visibility settings in the sample browser.

## Available Commands

### `test_column_defaults`

Tests the default column visibility settings and provides verification steps.

```
python manage.py test_column_defaults
```

### `reset_column_settings`

Generates JavaScript code that can be used to reset column settings in a browser.

```
python manage.py reset_column_settings
```

### `generate_default_columns`

Generates JavaScript code for manually setting the default column visibility.

```
python manage.py generate_default_columns
```

### `verify_column_settings`

Verifies consistency between the default column settings defined in management commands and in the JavaScript file.

```
python manage.py verify_column_settings
```

## Default Column Configuration

By default, the following columns are visible:

- FASTQ NAME
- STUDY SET
- LOAD NAME
- LIBRARY PREP METHOD
- ORGANISM COMMON NAME
- INGEST STATUS
- ALIGNMENT STATUS
- POSTQC STATUS

All other columns are hidden by default.

## Troubleshooting

If the column visibility settings are not working as expected:

1. Try using the "Reset to Default" button in the column settings dropdown
2. If that doesn't work, run `python manage.py reset_column_settings` and follow the instructions
3. Still having issues? Run `python manage.py generate_default_columns` and follow the instructions to manually set the defaults 