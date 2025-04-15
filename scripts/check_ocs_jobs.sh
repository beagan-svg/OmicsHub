#!/bin/bash
source /home/svc_bicore/genomics-cloud-services/gcs-cli/.venv/bin/activate
export AWS_PROFILE=aibs-bicore

echo "Checking alignment jobs..."
align_output=$(ocs core gwo demand list-demands --demand-type align --status IN_PROGRESS --format json)
if [ -z "$align_output" ] || [ "$align_output" = "[]" ] || [[ "$align_output" == *"No demands were found"* ]]; then
    align_jobs=0
else
    align_jobs=$(echo "$align_output" | jq length)
fi
echo "Found $align_jobs alignment jobs"

echo -e "\nChecking post-alignment jobs..."
postalign_output=$(ocs core gwo demand list-demands --demand-type post-align --status IN_PROGRESS --format json)
if [ -z "$postalign_output" ] || [ "$postalign_output" = "[]" ] || [[ "$postalign_output" == *"No demands were found"* ]]; then
    postalign_jobs=0
else
    postalign_jobs=$(echo "$postalign_output" | jq length)
fi
echo "Found $postalign_jobs post-alignment jobs"

total_jobs=$((align_jobs + postalign_jobs))
echo -e "\nTotal running jobs: $total_jobs"

# Print raw outputs for debugging
echo -e "\nRaw alignment output:"
echo "$align_output"
echo -e "\nRaw post-alignment output:"
echo "$postalign_output" 