#!/bin/bash

set -euo pipefail  # Safer scripting: stop on error, undefined var, or pipe failure
IFS=$'\n\t'

# Activate environment
source /home/svc_bicore/genomics-cloud-services/gcs-cli/.venv/bin/activate
export AWS_PROFILE=aibs-bicore

# Output metadata file
metadata_file="nwgc.csv"

# Column headers for the metadata file
header="Fastq Name,Library Prep Method,Study Set,Alignment Method,Amplification ID,Amplification,Batch Name,Batch Name From Vendor,Cell Capture,Cell Prep Type,Library Prep Method ID,Library Prep Name,Load Name,Organism Common Name,Organism Name,Sample ID,Sequencing Vendor"
echo "$header" > "$metadata_file"

# Fetch all batch metadata
json_output=$(ocs batches list NWGC --format json)

# Process each dataset
echo "$json_output" | jq -r '.[].dataset_name' | while read -r dataset_name; do
    batch_name=$(echo "$dataset_name" | awk -F'_' '{print $2}')
    echo "Processing batch: $batch_name"

    metadata_json=$(ocs fastqs list metadata --batch-name-from-vendor "$batch_name" --detail --format json)

    echo "$metadata_json" | jq -c '.[]' | while read -r record; do
        library_prep_method_name=$(jq -r '.library_prep_method_name' <<< "$record")

        # Skip batches with NexteraXT
        if [[ "$library_prep_method_name" == *"NexteraXT"* ]]; then
            echo "Skipping batch: $batch_name (Contains NexteraXT)"
            continue
        fi

        # Extract all required fields
        values=(
            "$(jq -r '.fastq_name' <<< "$record")"
            "$library_prep_method_name"
            "$(jq -r '.studies | join("+")' <<< "$record")"
            "$(jq -r '.alignment_method' <<< "$record")"
            "$(jq -r '.amplification_id' <<< "$record")"
            "$(jq -r '.amplification_name' <<< "$record")"
            "$(jq -r '.batch_name' <<< "$record")"
            "$(jq -r '.batch_name_from_vendor' <<< "$record")"
            "$(jq -r '.cell_capture' <<< "$record")"
            "$(jq -r '.cell_prep_type' <<< "$record")"
            "$(jq -r '.library_prep_method_id' <<< "$record")"
            "$(jq -r '.library_prep_name' <<< "$record")"
            "$(jq -r '.load_name' <<< "$record")"
            "$(jq -r '.organism_common_name' <<< "$record")"
            "$(jq -r '.organism_name' <<< "$record")"
            "$(jq -r '.sample_id' <<< "$record")"
            "$(jq -r '.sample_name' <<< "$record")"
            "$(jq -r '.sample_type' <<< "$record")"
            "$(jq -r '.sequencing_vendor' <<< "$record")"
        )

        # Join values into a CSV row
        IFS=','; echo "${values[*]}" >> "$metadata_file"
    done
done

echo "Done!"
