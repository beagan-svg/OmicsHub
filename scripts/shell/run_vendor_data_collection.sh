#!/bin/bash

set -euo pipefail  # Safer scripting: stop on error, undefined var, or pipe failure
IFS=$'\n\t'

# Define paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
DATA_DIR="$PROJECT_ROOT/data/csv"

# Create data directory if it doesn't exist
mkdir -p "$DATA_DIR"

# Function to run a vendor script
run_vendor_script() {
    local vendor=$1
    local script_path="$SCRIPT_DIR/$vendor.sh"
    local output_csv="$DATA_DIR/$vendor.csv"
    
    echo "================================================"
    echo "Running $vendor data collection script..."
    echo "================================================"
    
    # Change to the script directory to avoid path issues
    cd "$SCRIPT_DIR"
    
    # Run the vendor script
    bash "$script_path"
    
    # Check if CSV was created and move it to the data directory
    if [ -f "./$vendor.csv" ]; then
        echo "Moving $vendor.csv to $DATA_DIR"
        mv "./$vendor.csv" "$output_csv"
    else
        echo "Warning: $vendor.csv was not created!"
    fi
    
    echo "Completed $vendor data collection."
    echo ""
}

# Function to import data to database
import_data() {
    local source=$1
    local import_script="$PROJECT_ROOT/scripts/data_import/import_vendor_data.py"
    
    echo "================================================"
    echo "Importing $source data to database..."
    echo "================================================"
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Set up Python environment
    export PYTHONPATH=$PYTHONPATH:$(pwd)
    export DJANGO_SETTINGS_MODULE=config.settings.development
    
    # Activate virtual environment if it exists
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi
    
    # Run the import script
    python "$import_script" --source "$source" --no-clear
    
    echo "Completed importing $source data."
    echo ""
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
    echo "  --help              Show this help message"
    echo ""
    echo "Example:"
    echo "  $(basename "$0") --collect isilon --import isilon"
    echo "  $(basename "$0") --all"
}

# Main script
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

# Process command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --collect)
            source="$2"
            if [ "$source" == "all" ]; then
                run_vendor_script "isilon"
                run_vendor_script "nwgc"
                run_vendor_script "nygc"
            else
                run_vendor_script "$source"
            fi
            shift 2
            ;;
        --import)
            source="$2"
            import_data "$source"
            shift 2
            ;;
        --all)
            run_vendor_script "isilon"
            run_vendor_script "nwgc"
            run_vendor_script "nygc"
            import_data "all"
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

echo "All tasks completed successfully!" 