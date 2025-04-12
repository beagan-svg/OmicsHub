# Database Backups

This directory contains database backups organized by version.

## Structure

Backups are organized into subdirectories named after the version they represent:

```
backup_files/
├── v1.0.0/          # Initial version backups
├── v1.1.0/          # Future version backups
└── README.md        # This file
```

## Backup Files

### v1.0.0

- `status_tables_backup.sql`: SQL dump of status tables (alignment, postqc, ingest) - Created on April 6, 2025

## Backup Process

To create a new backup, use the following process:

1. Create a directory for the version:
   ```bash
   mkdir -p backup_files/v1.x.x
   ```

2. Backup the database tables:
   ```bash
   pg_dump -h localhost -U username -t tablename database_name > backup_files/v1.x.x/tablename_backup.sql
   ```

3. Add an entry to this README.md documenting the backup files.

## Restore Process

To restore a backup:

1. Navigate to the backup files directory:
   ```bash
   cd backup_files/v1.x.x
   ```

2. Import the SQL file:
   ```bash
   psql -h localhost -U username -d database_name -f tablename_backup.sql
   ```

## Notes

- All backups should include a timestamp in the filename or in a comment inside the file
- Large binary files should not be committed to version control
- Always test the restore process to ensure backup integrity 