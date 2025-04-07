#!/usr/bin/env python3
"""
PostQC script for RNA-Seq pipeline.
This script submits fastq files for post-alignment quality control.
"""

import sys
import subprocess
import json
import yaml
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join('logs', 'pipeline_postqc.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('postqc')

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)


def check_alignment_status(fastq_name):
    """
    Check if alignment is complete for a given fastq name.
    """
    try:
        logger.info(f"Checking alignment status for: {fastq_name}")
        command = [
            "ocs", "fastqs", "list", "metadata",
            "--fastq-name", fastq_name,
            "--include-metadata-field", "alignment_status",
            "--format", "json"
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to check alignment status: {result.stderr}")
            return False
            
        metadata = json.loads(result.stdout)
        if not metadata:
            logger.warning(f"No metadata returned for {fastq_name}")
            return False
            
        alignment_status = metadata[0].get("alignment_status", "").lower()
        
        if alignment_status == "completed":
            logger.info(f"Alignment is complete for {fastq_name}")
            return True
        else:
            logger.info(f"Alignment is not complete for {fastq_name}: {alignment_status}")
            return False
    except Exception as e:
        logger.error(f"Error checking alignment status: {e}")
        return False


def submit_postqc(fastq_name, config):
    """
    Submit a fastq file for PostQC processing.
    """
    try:
        logger.info(f"Submitting PostQC for: {fastq_name}")
        
        # PLACEHOLDER: Add actual PostQC submission command here
        # This is just a simulation for now
        logger.info(f"PostQC submission would happen here for {fastq_name}")
        
        # Simulate successful submission
        results_dir = Path('results')
        os.makedirs(results_dir, exist_ok=True)
        
        postqc_file = results_dir / "postqc_submissions.json"
        
        if postqc_file.exists():
            with open(postqc_file, 'r') as f:
                postqc_submissions = json.load(f)
        else:
            postqc_submissions = {}
            
        postqc_submissions[fastq_name] = {
            "status": "SUBMITTED",
            "timestamp": None
        }
        
        with open(postqc_file, 'w') as f:
            json.dump(postqc_submissions, f, indent=4)
            
        logger.info(f"PostQC submission recorded for {fastq_name}")
        return True
    except Exception as e:
        logger.error(f"Error submitting PostQC: {e}")
        return False


def main(config_file, fastq_name=None):
    """
    Main function to submit PostQC for completed alignments.
    """
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        if fastq_name:
            # Process a single fastq
            logger.info(f"Processing single fastq for PostQC: {fastq_name}")
            if check_alignment_status(fastq_name):
                if submit_postqc(fastq_name, config):
                    logger.info(f"PostQC submitted successfully for {fastq_name}")
                    return 0
                else:
                    logger.error(f"PostQC submission failed for {fastq_name}")
                    return 1
            else:
                logger.warning(f"Alignment not complete for {fastq_name}, skipping PostQC")
                return 2
        else:
            # Process all completed alignments from the results directory
            results_dir = Path('results')
            if not results_dir.exists():
                logger.error("Results directory does not exist")
                return 1
                
            # Find all running alignment files
            running_files = list(results_dir.glob("running_submitted_*.json"))
            if not running_files:
                logger.info("No alignment files found")
                return 0
                
            submitted_count = 0
            for file_path in running_files:
                with open(file_path, 'r') as f:
                    running_alignments = json.load(f)
                    
                for fastq_name, details in running_alignments.items():
                    status = details.get("Status", "")
                    
                    if status == "COMPLETED":
                        # Double-check the alignment status in the system
                        if check_alignment_status(fastq_name):
                            if submit_postqc(fastq_name, config):
                                logger.info(f"PostQC submitted successfully for {fastq_name}")
                                submitted_count += 1
                            else:
                                logger.error(f"PostQC submission failed for {fastq_name}")
                        else:
                            logger.warning(f"Alignment not complete for {fastq_name} according to metadata, skipping PostQC")
            
            logger.info(f"Submitted {submitted_count} samples for PostQC")
            return 0 if submitted_count > 0 else 0
    except Exception as e:
        logger.error(f"Error in PostQC process: {e}")
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python postqc.py <config_file> [fastq_name]")
        print("Example: python postqc.py ../config/pipeline_config.yaml MX102931")
        sys.exit(1)
        
    config_file = sys.argv[1]
    fastq_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    sys.exit(main(config_file, fastq_name)) 