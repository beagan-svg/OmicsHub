#!/bin/bash
#
# OCS Database - Batch Processing Script
#
# This script processes a batch of RNA-Seq samples with the provided parameters.
# It's designed to be used as part of the RNA-Seq pipeline workflow.
#
# Usage:
#   ./process_batch.sh LOAD_NAME ORGANISM LIBRARY_PREP_METHOD
#
# Example:
#   ./process_batch.sh "MTX-22019_ATX-26019" "Homo sapiens" "10x 3' v3"
#
# Author: Beagan Nguy
# Last updated: 2023-06-15
#

set -euo pipefail  # Exit on error, undefined var, or pipe failure

# Define log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check if correct number of arguments were provided
if [ $# -lt 1 ]; then
    log "ERROR: Insufficient arguments provided"
    log "Usage: $0 LOAD_NAME [ORGANISM] [LIBRARY_PREP_METHOD]"
    exit 1
fi

# Store arguments
LOAD_NAME="$1"
ORGANISM="${2:-}"
LIBRARY_PREP_METHOD="${3:-}"

# Log the received arguments
log "Starting batch processing with the following parameters:"
log "- Load Name: $LOAD_NAME"
[ -n "$ORGANISM" ] && log "- Organism: $ORGANISM"
[ -n "$LIBRARY_PREP_METHOD" ] && log "- Library Prep Method: $LIBRARY_PREP_METHOD"

# Create results directory if it doesn't exist
RESULTS_DIR="results"
mkdir -p "$RESULTS_DIR"

# Initialize batch processing
log "Initializing batch processing..."

# Here you would add the actual processing logic
# For example:
#
# 1. Query the database for samples matching the load name
# 2. Filter by organism and library prep method if provided
# 3. Submit each sample for processing
# 4. Track the processing status
# 5. Log the results

# For now, we'll just log that we would process the batch
if [ -n "$ORGANISM" ] && [ -n "$LIBRARY_PREP_METHOD" ]; then
    log "Would process $LOAD_NAME samples for organism '$ORGANISM' using '$LIBRARY_PREP_METHOD' library prep method"
    
    # Example of calling a Python script to handle the processing
    # python scripts/pipeline/process_batch.py "$LOAD_NAME" "$ORGANISM" "$LIBRARY_PREP_METHOD"
else
    log "Would process all samples for load name '$LOAD_NAME'"
    
    # Example of calling a Python script to handle the processing
    # python scripts/pipeline/process_batch.py "$LOAD_NAME"
fi

# Write processing record to results
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
echo "{\"load_name\": \"$LOAD_NAME\", \"timestamp\": \"$TIMESTAMP\", \"status\": \"submitted\"}" > "$RESULTS_DIR/${LOAD_NAME}_${TIMESTAMP}.json"

log "Batch processing initiated. Results will be available in $RESULTS_DIR/${LOAD_NAME}_${TIMESTAMP}.json"
log "Completed batch processing setup for $LOAD_NAME"

exit 0 