"""
Pipeline command generation utilities.
"""
import json
import os
import subprocess
import logging
import time
from pathlib import Path
from datetime import datetime
from .config import get_reference_name, get_chemistry
from viewer.models import Main

# Set up logging
logger = logging.getLogger(__name__)

def create_bash_script(commands, script_name='temp_script.sh'):
    """Create a temporary bash script with the given commands"""
    script_path = Path(os.path.join('/tmp', script_name))
    
    with open(script_path, 'w') as f:
        f.write('#!/bin/bash\n')
        f.write('source /home/svc_bicore/genomics-cloud-services/gcs-cli/.venv/bin/activate\n')
        f.write('export AWS_PROFILE=aibs-bicore\n\n')
        
        if isinstance(commands, list):
            for cmd in commands:
                f.write(f'{cmd}\n')
        else:
            f.write(f'{commands}\n')
    
    # Make script executable
    os.chmod(script_path, 0o755)
    
    return script_path

def run_bash_script(script_path):
    """Run a bash script and return its output"""
    try:
        # Read script content to determine if we should log or execute
        with open(script_path, 'r') as script_file:
            script_content = script_file.read()
        
        # Check if this is a submission command (that should be logged instead of executed)
        is_submission_command = False
        if 'align tenx-' in script_content:
            is_submission_command = True
        
        # For submission commands, log instead of executing
        if is_submission_command:
            # Create logs directory if it doesn't exist
            log_dir = Path('pipeline_command_logs')
            log_dir.mkdir(exist_ok=True)
            
            # Create log file with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_path = log_dir / f'command_log_{timestamp}.txt'
            
            with open(log_path, 'w') as log_file:
                log_file.write(f"--- COMMAND LOG AT {datetime.now().isoformat()} ---\n")
                log_file.write(f"Script path: {script_path}\n\n")
                log_file.write("Script content:\n")
                log_file.write(script_content)
                log_file.write("\n--- END OF COMMAND LOG ---\n")
            
            # Mock a successful submission response
            return json.dumps({
                "demand_status": "SUBMITTED", 
                "demand_id": f"test-demand-{timestamp}"
            })
        
        # For non-submission commands (like job tracking), actually execute
        output = subprocess.check_output([script_path], stderr=subprocess.STDOUT, universal_newlines=True)
        return output
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Script execution failed: {e.output}")
        return e.output
    except Exception as e:
        logger.error(f"Error with script: {str(e)}")
        return f"Error: {str(e)}"

def is_ingest_complete(fastq_name):
    """Check if ingest is complete for a given fastq name"""
    try:
        sample = Main.objects.get(fastq_name=fastq_name)
        return sample.ingest_status == 'Completed'
    except Main.DoesNotExist:
        return False

def determine_workflow(batch_name_from_vendor):
    """Determine workflow based on batch name from vendor"""
    if not batch_name_from_vendor:
        return None
    
    # Extract prefix (e.g., MTX from MTX-22030)
    parts = batch_name_from_vendor.split('-')
    if not parts:
        return None
    
    prefix = parts[0].upper()
    
    if prefix == 'MTX':
        return 'mtx'
    elif prefix == 'RTX':
        return 'rtx'
    else:
        return None

def create_mtx_alignment_command(sample):
    """Create MTX alignment command for a sample"""
    reference = get_reference_name(sample.get('organism_common_name', ''))
    load_name = sample.get('load_name', '')
    
    command = f'ocs fastqs align tenx-arc --reference-names "{reference}" --asset-name cellranger-arc --load-names "{load_name}" --notify-on FAILED --notify beagan.nguy@alleninstitute.org'
    
    return command

def create_rtx_alignment_command(sample):
    """Create RTX alignment command for a sample"""
    reference = get_reference_name(sample.get('organism_common_name', ''))
    load_name = sample.get('load_name', '')
    lib_prep = sample.get('library_prep', '')
    chemistry = get_chemistry(lib_prep)
    
    # Determine command based on library prep method
    if lib_prep in ['10xV3.1D', '10xRseq_Mult_noATAC', '10xV3.1_HT', '10Xv3.1']:
        command = f'ocs fastqs align tenx-rnaseq --reference-names "{reference}" --asset-name cellranger-rnaseq --load-names "{load_name}" --cellranger-addopts "--chemistry {chemistry} --include-introns"'
    elif lib_prep in ['10xV3.1_HT_CP', '10xV3.1_HT_CP-BC']:
        command = f'ocs fastqs align tenx-rnaseq-multi --asset-name cellranger-multi --reference-names "{reference}" --cellranger-addopts "--include-introns" --execution-priority HIGH --load-names "{load_name}"'
    elif lib_prep == '10xV4':
        command = f'ocs fastqs align tenx-rnaseq --reference-names "{reference}" --asset-name cellranger-rnaseq --load-names "{load_name}" --asset-tag 8.0.1 --cellranger-addopts "--chemistry {chemistry}"'
    else:
        logger.warning(f"Unknown library prep method: {lib_prep}, using default command")
        command = f'ocs fastqs align tenx-rnaseq --reference-names "{reference}" --asset-name cellranger-rnaseq --load-names "{load_name}" --cellranger-addopts "--chemistry {chemistry} --include-introns"'
    
    return command

def submit_sample_for_alignment(sample):
    """Submit a sample for alignment and return the result"""
    # Check if ingest is complete
    fastq_name = sample.get('fastq_name')
    if not is_ingest_complete(fastq_name):
        return {
            'status': 'error',
            'message': f'Ingest not complete for {fastq_name}',
            'fastq_name': fastq_name
        }
    
    # Get workflow from batch name
    batch_name = sample.get('batch_name_from_vendor', '')
    workflow = determine_workflow(batch_name)
    
    if not workflow:
        return {
            'status': 'error',
            'message': f'Could not determine workflow for {fastq_name} with batch name {batch_name}',
            'fastq_name': fastq_name
        }
    
    # Create alignment command based on workflow
    if workflow == 'mtx':
        command = create_mtx_alignment_command(sample)
    else:  # rtx
        command = create_rtx_alignment_command(sample)
    
    # Create and run bash script
    script_path = create_bash_script(command, f'submit_{fastq_name}.sh')
    output = run_bash_script(script_path)
    
    # Parse result
    try:
        # In test mode, output is already a JSON string
        result = json.loads(output)
        
        if 'demand_status' in result and result['demand_status'] == 'SUBMITTED':
            # Success
            return {
                'status': 'success',
                'message': f'Alignment submitted successfully for {fastq_name}',
                'fastq_name': fastq_name,
                'demand_id': result.get('demand_id', 'unknown'),
                'command': command
            }
        else:
            # Something went wrong
            return {
                'status': 'error',
                'message': f'Submission failed for {fastq_name}: {output}',
                'fastq_name': fastq_name
            }
    except json.JSONDecodeError:
        logger.error(f"Failed to parse submission output: {output}")
        # For test mode fallback
        if "Command logged" in output:
            return {
                'status': 'success',
                'message': f'Alignment command logged for {fastq_name}',
                'fastq_name': fastq_name,
                'demand_id': f'test-demand-{int(time.time())}',
                'command': command
            }
        return {
            'status': 'error',
            'message': f'Invalid response from OCS: {output}',
            'fastq_name': fastq_name
        } 