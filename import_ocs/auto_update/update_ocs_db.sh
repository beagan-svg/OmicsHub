#!/bin/bash

# Script to update the prod_ocs database by importing vendor data
# Uses the unified importer module through ocs_cli.py

# Determine script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Set up logging
LOG_DIR="$PROJECT_ROOT/import_ocs/logs"
mkdir -p $LOG_DIR
LOG_FILE="$LOG_DIR/update_ocs_db_$(date +\%Y\%m\%d).log"

# Command function for cleaner logging
run_command() {
    local cmd="$1"
    local log_msg="$2"
    
    echo "[$log_msg] $(date)" >> $LOG_FILE
    echo "Running: $cmd" >> $LOG_FILE
    eval "$cmd" >> $LOG_FILE 2>&1
    local status=$?
    
    if [ $status -eq 0 ]; then
        echo "Command completed successfully" >> $LOG_FILE
    else
        echo "Command failed with status $status" >> $LOG_FILE
    fi
    echo "" >> $LOG_FILE
    
    return $status
}

# Navigate to the project root directory
cd "$PROJECT_ROOT"

# Log start time
echo "=======================================" >> $LOG_FILE
echo "Starting database update at $(date)" >> $LOG_FILE

# Run the import based on the update type (specified by first argument)
update_type="${1:-all}"

case "$update_type" in
    "study")
        # Study JSON update only - for running every 2 hours
        echo "Running study JSON import only" >> $LOG_FILE
        run_command "python $PROJECT_ROOT/import_ocs/ocs_cli.py direct --file /allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json" "Importing study.json directly to database"
        ;;
    
    "vendor")
        # Vendor data update only - for running daily
        echo "Running vendor data collection and import" >> $LOG_FILE
        run_command "python $PROJECT_ROOT/import_ocs/ocs_cli.py collect --source all" "Collecting vendor data"
        run_command "python $PROJECT_ROOT/import_ocs/ocs_cli.py vendor --source all" "Importing vendor data to database"
        ;;
    
    "all"|*)
        # Full update - collect vendor data and import everything
        echo "Running full update (vendor collection + import, study import)" >> $LOG_FILE
        run_command "python $PROJECT_ROOT/import_ocs/ocs_cli.py all" "Running all-in-one import"
        ;;
esac

# Log completion
echo "Database update completed at $(date)" >> $LOG_FILE
echo "=======================================" >> $LOG_FILE
echo "" >> $LOG_FILE
