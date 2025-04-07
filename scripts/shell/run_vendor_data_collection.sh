#!/bin/bash
#
# OCS Database - Vendor Data Collection and Import
#
# This script automates the collection and import of vendor data from different sources.
# It can collect data from isilon, NWGC, NYGC, and other sources, process it,
# and import it into the OCS database.
#
# Features:
#   - Collects data from multiple vendor sources
#   - Imports data into database via Python scripts
#   - Handles environment setup automatically
#   - Supports individual operations (collect or import) or full workflows
#   - Provides detailed error handling and logging
#
# Usage:
#   ./scripts/shell/run_vendor_data_collection.sh [OPTIONS]
#
# Options:
#   --collect SOURCE    Collect data from SOURCE (isilon, nwgc, nygc, all)
#   --import SOURCE     Import data from SOURCE (isilon, nwgc, nygc, all)
#   --all               Collect and import from all sources
#   --debug             Enable debug mode (more verbose output)
#   --skip-venv         Skip virtual environment activation
#   --help              Show this help message
#
# Examples:
#   ./scripts/shell/run_vendor_data_collection.sh --collect isilon
#   ./scripts/shell/run_vendor_data_collection.sh --all
#

set -euo pipefail  # Safer scripting: stop on error, undefined var, or pipe failure
IFS=$'\n\t'

# Set default values
DEBUG=false
SKIP_VENV=false

# Define paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
DATA_DIR="$PROJECT_ROOT/data/csv"
LOG_DIR="$PROJECT_ROOT/logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/vendor_data_${TIMESTAMP}.log"

# Create required directories
mkdir -p "$DATA_DIR"
mkdir -p "$LOG_DIR"

# Logging function
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Error handling function
handle_error() {
    local exit_code=$?
    local line_number=$1
    log "ERROR" "Error on line $line_number: Command exited with status $exit_code"
    exit $exit_code
}

# Set up error trap
trap 'handle_error $LINENO' ERR

# Function to run a vendor script
run_vendor_script() {
    local vendor=$1
    local script_path="$SCRIPT_DIR/$vendor.sh"
    local output_csv="$DATA_DIR/$vendor.csv"
    
    log "INFO" "================================================"
    log "INFO" "Running $vendor data collection script..."
    log "INFO" "================================================"
    
    # Check if script exists
    if [ ! -f "$script_path" ]; then
        log "ERROR" "Script $script_path does not exist!"
        return 1
    fi
    
    # Change to the script directory to avoid path issues
    cd "$SCRIPT_DIR"
    
    # Run the vendor script with appropriate error handling
    if $DEBUG; then
        log "DEBUG" "Executing: bash $script_path"
        bash "$script_path" 2>&1 | tee -a "$LOG_FILE"
    else
        bash "$script_path" >> "$LOG_FILE" 2>&1
    fi
    
    # Check if CSV was created and move it to the data directory
    if [ -f "./$vendor.csv" ]; then
        log "INFO" "Moving $vendor.csv to $DATA_DIR"
        mv "./$vendor.csv" "$output_csv"
        
        # Log the record count
        record_count=$(( $(wc -l < "$output_csv") - 1 ))
        log "INFO" "Collected $record_count records from $vendor"
    else
        log "WARNING" "$vendor.csv was not created by the script!"
        return 1
    fi
    
    log "INFO" "Completed $vendor data collection."
    log "INFO" ""
    return 0
}

# Function to import data to database
import_data() {
    local source=$1
    local import_script="$PROJECT_ROOT/scripts/data_import/import_vendor_data.py"
    
    log "INFO" "================================================"
    log "INFO" "Importing $source data to database..."
    log "INFO" "================================================"
    
    # Check if import script exists
    if [ ! -f "$import_script" ]; then
        log "ERROR" "Import script $import_script does not exist!"
        return 1
    }
    
    # Check if CSV file exists for the source
    if [ "$source" != "all" ] && [ ! -f "$DATA_DIR/$source.csv" ]; then
        log "ERROR" "CSV file $DATA_DIR/$source.csv does not exist!"
        return 1
    fi
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Set up Python environment
    log "INFO" "Setting up Python environment..."
    if [ -z "${PYTHONPATH:-}" ]; then
        export PYTHONPATH=$(pwd)
    else
        export PYTHONPATH=$PYTHONPATH:$(pwd)
    fi
    export DJANGO_SETTINGS_MODULE=config.settings.development
    
    # Activate virtual environment if it exists and not skipped
    if [ -f "venv/bin/activate" ] && [ "$SKIP_VENV" = false ]; then
        log "INFO" "Activating virtual environment..."
        source venv/bin/activate
    fi
    
    # Run the import script with appropriate options
    local cmd_options="--source $source --no-clear"
    if $DEBUG; then
        cmd_options="$cmd_options --debug"
    fi
    
    log "INFO" "Running: python $import_script $cmd_options"
    if $DEBUG; then
        python "$import_script" $cmd_options 2>&1 | tee -a "$LOG_FILE"
    else
        python "$import_script" $cmd_options >> "$LOG_FILE" 2>&1
    fi
    
    log "INFO" "Completed importing $source data."
    log "INFO" ""
    return 0
}

# Show help message
show_help() {
    echo "Usage: $(basename "$0") [OPTIONS]"
    echo ""
    echo "Collect and import vendor data from different sources."
    echo ""
    echo "Options:"
    echo "  --collect SOURCE    Collect data from SOURCE (isilon, nwgc, nygc, all)"
    echo "  --import SOURCE     Import data from SOURCE (isilon, nwgc, nygc, all)"
    echo "  --all               Collect and import from all sources"
    echo "  --debug             Enable debug mode (more verbose output)"
    echo "  --skip-venv         Skip virtual environment activation"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") --collect isilon --import isilon"
    echo "  $(basename "$0") --all"
    echo ""
    echo "Log files are stored in $LOG_DIR"
}

# Process command-line arguments
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --collect)
            if [ -z "${2:-}" ]; then
                log "ERROR" "Missing argument for --collect"
                exit 1
            fi
            source="$2"
            if [ "$source" == "all" ]; then
                log "INFO" "Collecting data from all sources..."
                run_vendor_script "isilon" || log "WARNING" "Failed to collect isilon data"
                run_vendor_script "nwgc" || log "WARNING" "Failed to collect nwgc data"
                run_vendor_script "nygc" || log "WARNING" "Failed to collect nygc data"
            else
                run_vendor_script "$source" || log "WARNING" "Failed to collect $source data"
            fi
            shift 2
            ;;
        --import)
            if [ -z "${2:-}" ]; then
                log "ERROR" "Missing argument for --import"
                exit 1
            fi
            source="$2"
            import_data "$source" || log "WARNING" "Failed to import $source data"
            shift 2
            ;;
        --all)
            log "INFO" "Running full workflow for all sources..."
            # Collect from all sources
            run_vendor_script "isilon" || log "WARNING" "Failed to collect isilon data"
            run_vendor_script "nwgc" || log "WARNING" "Failed to collect nwgc data"
            run_vendor_script "nygc" || log "WARNING" "Failed to collect nygc data"
            
            # Import all collected data
            import_data "all" || log "WARNING" "Failed to import all data"
            shift
            ;;
        --debug)
            DEBUG=true
            log "INFO" "Debug mode enabled"
            shift
            ;;
        --skip-venv)
            SKIP_VENV=true
            log "INFO" "Virtual environment activation skipped"
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log "ERROR" "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

log "INFO" "All tasks completed!"
log "INFO" "Log file: $LOG_FILE"

exit 0 