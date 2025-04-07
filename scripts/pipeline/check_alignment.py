#!/usr/bin/env python3
"""
Alignment monitoring script for RNA-Seq pipeline.
This script checks the status of running alignments and updates the status file.
"""

import sys
import subprocess
import json
import yaml
import os
import logging
import time
import glob
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join('logs', 'pipeline_monitor.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('monitor')

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)


def check_demand_status(demand_id):
    """
    Check the status of a demand using the OCS CLI.
    """
    try:
        logger.info(f"Checking status for demand ID: {demand_id}")
        command = [
            "ocs", "demands", "describe",
            "--id", demand_id,
            "--format", "json"
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to check demand status: {result.stderr}")
            return None
            
        demand_info = json.loads(result.stdout)
        status = demand_info.get("status", "UNKNOWN")
        logger.info(f"Status for demand {demand_id}: {status}")
        return status
    except Exception as e:
        logger.error(f"Error checking demand status: {e}")
        return None


def update_alignment_status():
    """
    Check and update the status of all running alignments.
    """
    try:
        results_dir = Path('results')
        if not results_dir.exists():
            logger.warning("Results directory does not exist")
            return
            
        # Find all running alignment files
        running_files = glob.glob(str(results_dir / "running_submitted_*.json"))
        if not running_files:
            logger.info("No running alignment files found")
            return
            
        for file_path in running_files:
            logger.info(f"Checking alignments in file: {file_path}")
            
            with open(file_path, 'r') as f:
                running_alignments = json.load(f)
                
            updated = False
                
            for fastq_name, details in running_alignments.items():
                demand_id = details.get("demand_id")
                current_status = details.get("Status", "")
                
                # Skip already completed or failed demands
                if current_status in ["COMPLETED", "FAILED", "CANCELLED"]:
                    continue
                    
                # Check current status
                if demand_id and demand_id != "N/A":
                    status = check_demand_status(demand_id)
                    if status and status != current_status:
                        logger.info(f"Updating status for {fastq_name}: {current_status} -> {status}")
                        running_alignments[fastq_name]["Status"] = status
                        running_alignments[fastq_name]["last_updated"] = datetime.now().isoformat()
                        updated = True
                        
                        # If status is COMPLETED, we could trigger the next step (postQC)
                        if status == "COMPLETED":
                            logger.info(f"Alignment completed for {fastq_name}, ready for PostQC")
                            # TODO: Add code to trigger PostQC
                            
            # Save updates if any statuses changed
            if updated:
                with open(file_path, 'w') as f:
                    json.dump(running_alignments, f, indent=4)
                logger.info(f"Updated status file: {file_path}")
    except Exception as e:
        logger.error(f"Error updating alignment status: {e}")


def main(config_file, interval_minutes=30, single_run=False):
    """
    Main function to continuously monitor alignments at specified intervals.
    """
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            
        interval_minutes = config.get("settings", {}).get("alignment", {}).get("check_interval_minutes", interval_minutes)
        logger.info(f"Starting alignment monitoring (interval: {interval_minutes} minutes)")
        
        # Convert minutes to seconds for sleep
        interval_seconds = interval_minutes * 60
        
        if single_run:
            update_alignment_status()
            return
            
        # Continuous monitoring loop
        while True:
            update_alignment_status()
            logger.info(f"Sleeping for {interval_minutes} minutes")
            time.sleep(interval_seconds)
            
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Error in monitoring process: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_alignment.py <config_file> [--once]")
        print("Example: python check_alignment.py ../config/pipeline_config.yaml")
        sys.exit(1)
        
    config_file = sys.argv[1]
    single_run = "--once" in sys.argv
    
    sys.exit(main(config_file, single_run=single_run)) 