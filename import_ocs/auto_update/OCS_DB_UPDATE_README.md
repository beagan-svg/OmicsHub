# OCS Database Automated Update System

This system automates the process of updating your prod_ocs database by running different import tasks at scheduled intervals:
- Importing study.json every 2 hours
- Collecting and importing vendor data once daily

## Components

1. **update_ocs_db.sh** - A shell script that runs the appropriate import commands based on the task type
2. **ocs_db_crontab.txt** - Contains the crontab entries to schedule the different import tasks
3. **ocs_cli.py** - The command-line interface used by the update script to perform imports

## Update Types

The system supports three types of updates:

1. **Study Update** (Every 2 Hours):
   - Imports the study.json file directly to the database using direct SQL mode
   - Command: `update_ocs_db.sh study`

2. **Vendor Update** (Daily):
   - Collects vendor data from all sources
   - Imports the collected vendor data into the database
   - Command: `update_ocs_db.sh vendor`

3. **Full Update** (Manual or on demand):
   - Performs both vendor collection/import and study.json import
   - Command: `update_ocs_db.sh all` or just `update_ocs_db.sh`

## Setup Instructions

### 1. Verify Configuration (Optional)

The update script is pre-configured to use the ocs_cli.py interface for all operations. If needed, you can customize:

- Edit `/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs/import_ocs/auto_update/update_ocs_db.sh`
- Modify the commands in the case statement to use different options

### 2. Set Up the Cron Jobs

To schedule the script to run automatically:

1. Open your crontab for editing:
   ```bash
   crontab -e
   ```

2. Add the lines from the `ocs_db_crontab.txt` file:
   ```
   # Run study.json import every 2 hours
   0 */2 * * * /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs/import_ocs/auto_update/update_ocs_db.sh study

   # Run vendor data collection and import daily at 1 AM
   0 1 * * * /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs/import_ocs/auto_update/update_ocs_db.sh vendor
   ```

3. Save and exit the editor.

The script will now run automatically according to the schedule.

### 3. Customizing the Schedule (Optional)

If you want to run the tasks at different intervals:

- Edit the crontab entries with your preferred schedule
- Study updates: Currently runs every 2 hours (`0 */2 * * *`)
- Vendor updates: Currently runs at 1 AM daily (`0 1 * * *`)

## Checking Logs

The script creates log files in:
```
/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs/import_ocs/logs/
```

Log files are named with the date format `update_ocs_db_YYYYMMDD.log`.

To view the most recent log:
```bash
tail -f /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs/import_ocs/logs/update_ocs_db_$(date +%Y%m%d).log
```

## Troubleshooting

### Script Not Running

1. Check if the cron service is running:
   ```bash
   systemctl status cron
   ```

2. Verify your crontab entries:
   ```bash
   crontab -l
   ```

3. Make sure the script is executable:
   ```bash
   chmod +x /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs/import_ocs/auto_update/update_ocs_db.sh
   ```

### Import Errors

1. Check the log files for error messages.

2. Try running the script manually with a specific type:
   ```bash
   # For study.json import
   /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs/import_ocs/auto_update/update_ocs_db.sh study
   
   # For vendor data import
   /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs/import_ocs/auto_update/update_ocs_db.sh vendor
   ```

3. Verify that the required files exist in the expected locations:
   - study.json: `/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json`
   - Vendor CSV files: Will be collected to `/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs/import_ocs/data/csv/`

## Important Notes

1. **Status Preservation**: The import system preserves COMPLETED statuses, meaning it will never downgrade a status that is already marked as COMPLETED.

2. **Direct SQL Mode**: For study.json imports, the script uses the direct SQL mode which is faster than the Django ORM method.

3. **Consolidated Imports**: The system now uses the consolidated ocs_database_importer.py via the ocs_cli.py interface, providing better error handling and file path suggestions.
