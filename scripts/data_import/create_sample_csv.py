#!/usr/bin/env python
"""
OCS Database - Sample CSV Generator

This script creates a small sample CSV file that can be used to test the vendor data import process.
It generates random-ish data that matches the expected format of vendor CSV files.

Usage:
    python scripts/data_import/create_sample_csv.py [output_file]
    
Arguments:
    output_file    Optional. Path to the output CSV file. Default: data/csv/sample.csv
"""

import os
import sys
import csv
import random
from datetime import datetime

# Set up paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
default_output = os.path.join(project_root, 'data', 'csv', 'sample.csv')

# Make sure the data/csv directory exists
os.makedirs(os.path.dirname(default_output), exist_ok=True)

# CSV headers
headers = [
    "Fastq Name", "Library Prep Method", "Study Set", "Alignment Method",
    "Amplification ID", "Amplification", "Batch Name", "Batch Name From Vendor",
    "Cell Capture", "Cell Prep Type", "Library Prep Method ID", "Library Prep Name",
    "Load Name", "Organism Common Name", "Organism Name", "Sample ID", "Sequencing Vendor"
]

# Sample data generation
def generate_sample_data(num_records=10):
    """Generate sample data for testing."""
    organisms = ["human", "mouse", "macaque"]
    library_preps = ["10x_v3", "10x_v2", "Smart-seq", "Smart-seq2"]
    studies = ["Brain_survey", "Brain_Ref", "M1_study", "Hu_Ref_Brain", "Mouse_V1"]
    
    records = []
    for i in range(num_records):
        # Generate a random-ish fastq name
        fastq_name = f"SAMPLE-{i+1:04d}"
        
        # Select random values for other fields
        organism = random.choice(organisms)
        library_prep = random.choice(library_preps)
        study_set = "+".join(random.sample(studies, k=random.randint(1, 2)))
        
        record = {
            "Fastq Name": fastq_name,
            "Library Prep Method": library_prep,
            "Study Set": study_set,
            "Alignment Method": "aln_v3",
            "Amplification ID": f"AMP-{i+1:03d}",
            "Amplification": "PCR",
            "Batch Name": f"BATCH-{random.randint(1, 5):03d}",
            "Batch Name From Vendor": f"VND-BATCH-{random.randint(1, 5):03d}",
            "Cell Capture": "10x",
            "Cell Prep Type": "Nuclei",
            "Library Prep Method ID": f"LIB-{random.randint(1, 100):03d}",
            "Library Prep Name": f"LIB-{library_prep}",
            "Load Name": f"LOAD-{random.randint(1, 10):03d}",
            "Organism Common Name": organism.capitalize(),
            "Organism Name": organism,
            "Sample ID": f"S-{i+1:04d}",
            "Sequencing Vendor": random.choice(["NYGC", "NWGC", "Isilon"])
        }
        records.append(record)
    
    return records

def write_csv(records, output_file):
    """Write records to a CSV file."""
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(records)

def main():
    """Main execution function."""
    # Determine output file path
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    else:
        output_file = default_output
    
    # Generate sample data
    print(f"Generating sample CSV file with 10 records...")
    records = generate_sample_data(10)
    
    # Write to CSV
    write_csv(records, output_file)
    print(f"Sample CSV file created: {output_file}")
    print(f"You can test the import process with:")
    print(f"python scripts/data_import/import_vendor_data.py --source sample --dry-run")
    print(f"python scripts/data_import/import_vendor_data.py --source sample")

if __name__ == "__main__":
    main() 