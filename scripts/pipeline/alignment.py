#!/usr/bin/env python3
"""
Alignment script for RNA-Seq pipeline.
This script submits fastq files for alignment based on the configuration.
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
        logging.FileHandler(os.path.join('logs', 'pipeline_alignment.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('alignment')

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)
os.makedirs('results', exist_ok=True)


def get_fastq_names(batch_name):
    """
    Get all fastq_name values for a given batch_name using the OCS CLI.
    """
    try:
        logger.info(f"Retrieving fastq names for batch: {batch_name}")
        command = [
            "ocs", "fastqs", "list", "metadata",
            "--batch-name-from-vendor", batch_name,
            "--format", "json"
        ]
        logger.debug(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to run command: {result.stderr}")
        
        metadata = json.loads(result.stdout)
        fastq_names = [entry["fastq_name"] for entry in metadata]
        logger.info(f"Found {len(fastq_names)} fastq names")
        return fastq_names
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON for batch '{batch_name}': {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Error retrieving fastq names: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
def extract_metadata(fastq_name, save_metadata=False, output_dir=None):
    """
    Extract metadata for a given FASTQ name using the OCS CLI.
    """
    try:
        logger.info(f"Extracting metadata for fastq: {fastq_name}")
        command = [
            "ocs", "fastqs", "list", "metadata",
            "--fastq-name", fastq_name,
            "--include-metadata-field", "organism_common_name",
            "--include-metadata-field", "library_prep_method_name",
            "--format", "json"
        ]
        logger.debug(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to run command: {result.stderr}")
            
        metadata = json.loads(result.stdout)

        if save_metadata and output_dir:
            os.makedirs(output_dir, exist_ok=True)
            metadata_file = os.path.join(output_dir, f"{fastq_name}_metadata.json")
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=4)
            logger.info(f"Metadata saved to: {metadata_file}")

        return metadata
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON for {fastq_name}: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Error extracting metadata: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

def generate_command(metadata, workflow, config):
    """
    Generate the OCS alignment command based on metadata and workflow type.
    """
    try:
        logger.info(f"Generating command for workflow: {workflow}")
        workflow_config = config.get("workflows", {}).get(workflow)
        if not workflow_config:
            raise ValueError(f"Workflow '{workflow}' not defined in config")
            
        references = config["references"]
        chemistries = config["chemistries"]
        
        load_name = metadata[0]["load_name"]
        organism = metadata[0]["organism_common_name"]
        library_prep = metadata[0]["library_prep_method_name"]
        
        notification_email = config.get("settings", {}).get("notifications", {}).get("email", {}).get("recipients", ["beagan.nguy@alleninstitute.org"])[0]

        if workflow == "mtx":
            reference = references.get(organism, "unknown")
            if reference == "unknown":
                raise ValueError(f"Unknown organism '{organism}' for MTX workflow")
                
            command = workflow_config["command_template"].format(
                reference=reference,
                load_name=load_name,
                notification_email=notification_email
            )
            return command
            
        elif workflow == "rtx":
            reference = references.get(organism, "unknown")
            if reference == "unknown":
                raise ValueError(f"Unknown organism '{organism}' for RTX workflow")
                
            if library_prep in chemistries:
                chemistry = chemistries[library_prep]
                command = workflow_config["command_template"].format(
                    reference=reference,
                    load_name=load_name,
                    chemistry=chemistry
                )
                return command
            else:
                raise ValueError(f"Unknown library prep method '{library_prep}'")
        else:
            raise ValueError(f"Unknown workflow type '{workflow}'")
            
    except KeyError as e:
        error_msg = f"Missing required configuration or metadata field: {e}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"Error generating command: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

def parse_json_and_update(sub_log_json, output_file, fastq_name=None):
    """
    Parse alignment submission results and update the running alignments file.
    """
    try:
        # Extract demand_id
        demand_id = sub_log_json.get("demand_execution", {}).get("demand_id", "N/A")

        # Extract FASTQ_NAMES
        fastq_set = sub_log_json.get("demand_execution", {}).get("execution_parameters", {}).get("params", {}).get("FASTQ_NAMES", "")

        # Parse FASTQ_NAMES to extract values containing 'MX'
        mtx_fastq = fastq_name
        if not mtx_fastq:
            for fastq_name_entry in fastq_set.split(','):
                if 'MX' in fastq_name_entry:
                    mtx_fastq = fastq_name_entry.split('=')[1]
                    break
        
        if not mtx_fastq:
            logger.warning(f"Could not find fastq name in submission response")
            mtx_fastq = "unknown"
            
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Load existing data if the file exists
        if os.path.exists(output_file):
            with open(output_file, 'r') as outfile:
                running_alignments_json = json.load(outfile)
        else:
            running_alignments_json = dict()

        # Update the JSON with demand_id and Status
        running_alignments_json[mtx_fastq] = {
            "demand_id": demand_id,
            "Status": "SUBMITTED",
            "timestamp": sub_log_json.get("demand_timestamp", "")
        }

        with open(output_file, 'w') as f:
            json.dump(running_alignments_json, f, indent=4)
            
        logger.info(f"Updated running alignments file: {output_file}")
    except Exception as e:
        logger.error(f"Error updating running alignments file: {e}")


def submit_command(command, batch_line, fastq_name=None):
    """
    Submit the alignment command to the OCS system.
    """
    try:
        logger.info(f"Submitting command: {command}")
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Command execution failed: {result.stderr}")
            return False

        submit_log = json.loads(result.stdout)
        # "results/running_alignments.json" contains a list of fastq names and their demand id
        output_file = f"results/running_submitted_{batch_line}.json"
        parse_json_and_update(submit_log, output_file, fastq_name)
        
        if submit_log.get("demand_status") == "SUBMITTED":
            logger.info(f"Command submitted successfully")
            return True
        else:
            logger.warning(f"Command submission status: {submit_log.get('demand_status')}")
            return False
    except Exception as e:
        logger.error(f"Error submitting command: {e}")
        return False
    

def check_ingest_status(fastq_name):
    """
    Check if ingest is complete for a given fastq name.
    """
    try:
        logger.info(f"Checking ingest status for: {fastq_name}")
        command = [
            "ocs", "fastqs", "list", "metadata",
            "--fastq-name", fastq_name,
            "--include-metadata-field", "ingest_status",
            "--format", "json"
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to check ingest status: {result.stderr}")
            return False
            
        metadata = json.loads(result.stdout)
        if not metadata:
            logger.warning(f"No metadata returned for {fastq_name}")
            return False
            
        ingest_status = metadata[0].get("ingest_status", "").lower()
        
        if ingest_status == "completed":
            logger.info(f"Ingest is complete for {fastq_name}")
            return True
        else:
            logger.info(f"Ingest is not complete for {fastq_name}: {ingest_status}")
            return False
    except Exception as e:
        logger.error(f"Error checking ingest status: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python alignment.py <batch_line> <workflow> <config_file> [fastq_name]")
        print("Example: python alignment.py \"MTX-22019_ATX-26019\" mtx ../configs/config.yaml")
        sys.exit(1)
    
    batch_name = sys.argv[1]
    workflow = sys.argv[2]
    config_file = sys.argv[3]
    specific_fastq = None if len(sys.argv) < 5 else sys.argv[4]
   
    logger.info(f"Starting alignment process for batch: {batch_name}, workflow: {workflow}")
    
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        if specific_fastq:
            # Process a single fastq
            logger.info(f"Processing single fastq: {specific_fastq}")
            if check_ingest_status(specific_fastq):
                metadata = extract_metadata(specific_fastq, save_metadata=True, output_dir="results")
                command = generate_command(metadata, workflow, config)
                if submit_command(command, batch_name, specific_fastq):
                    logger.info(f"Alignment submitted successfully for {specific_fastq}")
                    sys.exit(0)
                else:
                    logger.error(f"Alignment submission failed for {specific_fastq}")
                    sys.exit(1)
            else:
                logger.warning(f"Ingest not complete for {specific_fastq}, skipping alignment")
                sys.exit(2)
        else:
            # Process all fastqs in the batch
            fastq_list = get_fastq_names(batch_name)
            submitted_count = 0
            
            for fastq_name in fastq_list:
                if check_ingest_status(fastq_name):
                    metadata = extract_metadata(fastq_name, save_metadata=True, output_dir="results")
                    command = generate_command(metadata, workflow, config)
                    if submit_command(command, batch_name, fastq_name):
                        logger.info(f"Alignment submitted successfully for {fastq_name}")
                        submitted_count += 1
                    else:
                        logger.error(f"Alignment submission failed for {fastq_name}")
                else:
                    logger.warning(f"Ingest not complete for {fastq_name}, skipping alignment")
            
            if submitted_count > 0:
                logger.info(f"Successfully submitted {submitted_count} out of {len(fastq_list)} fastqs for alignment")
                sys.exit(0)
            else:
                logger.error(f"Failed to submit any fastqs for alignment")
                sys.exit(1)
                
    except Exception as e:
        logger.error(f"Error in alignment process: {e}")
        sys.exit(1) 