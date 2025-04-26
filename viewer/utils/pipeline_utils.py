import json
import os
import subprocess
import yaml
import logging
from pathlib import Path
from datetime import datetime
import time
from django.conf import settings
from django.utils import timezone
from viewer.core.models import Alignment, PostQC, Metadata, Main

# Set up logging
logger = logging.getLogger(__name__)

# Path to pipeline configuration file
PIPELINE_CONFIG_PATH = Path(os.path.join('config', 'pipeline_config.yaml'))

def load_pipeline_config():
    """Load pipeline configuration from yaml file"""
    if PIPELINE_CONFIG_PATH.exists():
        with open(PIPELINE_CONFIG_PATH, 'r') as f:
            try:
                return yaml.safe_load(f)
            except Exception as e:
                logger.error(f"Error loading pipeline config: {str(e)}")
                return {}
    else:
        # Return default configuration
        return {
            "references": {
                "armadillo": "armadillo_ncbi_mdasnov1-hap2_genome_star2-7-1a",
                "human": "human_10x_grch38_genome_star2.7.1a",
                "mouse": "mouse_10x_mm10_genome_star2.7.1a",
            },
            "chemistries": {
                "10xV3.1D": "SC3Pv3",
                "10xRseq_Mult_noATAC": "ARC-v1",
                "10xV3.1_HT": "SC3Pv3HT",
                "10xV4": "SC3Pv4",
                "10Xv2": "SC3Pv2"
            }
        }

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

def count_running_jobs():
    """Count the number of running alignment and post-align jobs"""
    align_count = 0
    post_align_count = 0
    
    # Check alignment jobs
    script_path = create_bash_script(
        'ocs core gwo demand list-demands --demand-type align --status IN_PROGRESS --format json',
        'check_align_jobs.sh'
    )
    output = run_bash_script(script_path)
    
    try:
        if 'No demands were found' not in output and output.strip():
            align_jobs = json.loads(output)
            if isinstance(align_jobs, list):
                align_count = len(align_jobs)
            else:
                logger.error(f"Unexpected alignment jobs output format: {output}")
    except json.JSONDecodeError:
        logger.error(f"Failed to parse alignment jobs output: {output}")
    except Exception as e:
        logger.error(f"Error counting alignment jobs: {str(e)}")
    
    # Check post-alignment jobs
    script_path = create_bash_script(
        'ocs core gwo demand list-demands --demand-type post-align --status IN_PROGRESS --format json',
        'check_post_align_jobs.sh'
    )
    output = run_bash_script(script_path)
    
    try:
        if 'No demands were found' not in output and output.strip():
            post_align_jobs = json.loads(output)
            if isinstance(post_align_jobs, list):
                post_align_count = len(post_align_jobs)
            else:
                logger.error(f"Unexpected post-alignment jobs output format: {output}")
    except json.JSONDecodeError:
        logger.error(f"Failed to parse post-alignment jobs output: {output}")
    except Exception as e:
        logger.error(f"Error counting post-alignment jobs: {str(e)}")
    
    # Also update database to match actual running jobs
    update_all_running_jobs()
    
    return {
        'align_count': align_count,
        'post_align_count': post_align_count,
        'total': align_count + post_align_count
    }

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

def get_reference_name(organism_common_name):
    """Get reference name for an organism"""
    config = load_pipeline_config()
    references = config.get('references', {})
    
    # Normalize organism name (lowercase, replace spaces with underscores)
    normalized_name = organism_common_name.lower().replace(' ', '_')
    
    # Try direct lookup first
    if normalized_name in references:
        return references[normalized_name]
    
    # Try partial matching
    for key in references:
        if key in normalized_name or normalized_name in key:
            return references[key]
    
    # Default to human if no match
    logger.warning(f"No reference found for organism: {organism_common_name}, using human as default")
    return references.get('human', 'human_10x_grch38_genome_star2.7.1a')

def get_chemistry(library_prep_method):
    """Get chemistry value for a library prep method"""
    config = load_pipeline_config()
    chemistries = config.get('chemistries', {})
    
    # Try direct lookup
    if library_prep_method in chemistries:
        return chemistries[library_prep_method]
    
    # Default to SC3Pv3 if no match
    logger.warning(f"No chemistry found for library prep: {library_prep_method}, using SC3Pv3 as default")
    return chemistries.get('10xV3.1D', 'SC3Pv3')

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

def check_alignment_status(demand_id):
    """Check the status of an alignment job"""
    command = f'ocs core gwo demand get-status --demand-id {demand_id} --format json'
    script_path = create_bash_script(command, f'check_status_{demand_id}.sh')
    output = run_bash_script(script_path)
    
    try:
        if output and 'demand_id' in output:
            status_json = json.loads(output)
            if isinstance(status_json, list) and len(status_json) > 0:
                status = status_json[0].get('status', 'UNKNOWN')
                start_time = status_json[0].get('start_time', '')
                
                return {
                    'status': 'success',
                    'demand_id': demand_id,
                    'job_status': status,
                    'start_time': start_time
                }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error checking status for demand_id {demand_id}: {str(e)}',
            'demand_id': demand_id
        }
    
    return {
        'status': 'error',
        'message': f'Could not retrieve status for demand_id {demand_id}',
        'demand_id': demand_id
    }

def stop_alignment_job(demand_id):
    """Stop an alignment job"""
    command = f'ocs core gwo demand stop --demand-id {demand_id} --format json'
    script_path = create_bash_script(command, f'stop_job_{demand_id}.sh')
    output = run_bash_script(script_path)
    
    # Check if job was stopped successfully
    check_result = check_alignment_status(demand_id)
    
    if check_result.get('status') == 'success' and check_result.get('job_status') == 'ABORTED':
        return {
            'status': 'success',
            'message': f'Successfully stopped job with demand_id {demand_id}',
            'demand_id': demand_id
        }
    else:
        return {
            'status': 'error',
            'message': f'Failed to stop job with demand_id {demand_id}',
            'demand_id': demand_id
        }

def update_all_running_jobs():
    """Update status of all running jobs in the database"""
    results = []
    
    # Get all jobs marked as running in our database
    running_jobs = Alignment.objects.filter(status_id__in=['SUBMITTED', 'IN_PROGRESS'])
    
    # Check actual running jobs from the service
    script_path = create_bash_script(
        'ocs core gwo demand list-demands --demand-type align --status IN_PROGRESS --format json',
        'check_running_jobs.sh'
    )
    output = run_bash_script(script_path)
    
    try:
        actual_running_jobs = []
        if 'No demands were found' not in output and output.strip():
            actual_running_jobs = json.loads(output)
        
        # Create a set of actually running demand_ids
        actual_running_demand_ids = {job['demand_id'] for job in actual_running_jobs}
        
        # Update jobs that are no longer running
        for job in running_jobs:
            if job.demand_id not in actual_running_demand_ids:
                # Job is no longer running, mark as FAILED
                job.status_id = 'FAILED'
                job.end_time = timezone.now()
                job.save()
                
                # Update main table
                try:
                    main = Main.objects.get(fastq_name=job.fastq_name)
                    main.alignment_status = 'Failed'
                    main.save()
                except Main.DoesNotExist:
                    pass
                
                results.append({
                    'fastq_name': job.fastq_name_id,
                    'demand_id': job.demand_id,
                    'old_status': 'IN_PROGRESS',
                    'new_status': 'FAILED'
                })
        
        # Update or create entries for actually running jobs
        for running_job in actual_running_jobs:
            demand_id = running_job['demand_id']
            
            # Try to find the alignment record
            alignment = Alignment.objects.filter(demand_id=demand_id).first()
            
            if alignment:
                # Update existing record if status changed
                if alignment.status_id != 'IN_PROGRESS':
                    alignment.status_id = 'IN_PROGRESS'
                    alignment.save()
                    
                    # Update main table
                    try:
                        main = Main.objects.get(fastq_name=alignment.fastq_name)
                        main.alignment_status = 'In Progress'
                        main.save()
                    except Main.DoesNotExist:
                        pass
                    
                    results.append({
                        'fastq_name': alignment.fastq_name_id,
                        'demand_id': demand_id,
                        'old_status': alignment.status_id,
                        'new_status': 'IN_PROGRESS'
                    })
            
    except json.JSONDecodeError:
        logger.error(f"Failed to parse running jobs output: {output}")
    
    return results 

def get_queue_data():
    """Get data for samples in the processing queue"""
    try:
        # Get alignment queue data
        align_script = create_bash_script(
            'ocs core gwo demand list-demands --demand-type align --status IN_PROGRESS --format json',
            'get_align_queue.sh'
        )
        align_output = run_bash_script(align_script)
        
        # Get post-align queue data
        post_align_script = create_bash_script(
            'ocs core gwo demand list-demands --demand-type post-align --status IN_PROGRESS --format json',
            'get_post_align_queue.sh'
        )
        post_align_output = run_bash_script(post_align_script)
        
        # Process alignment queue
        alignment_queue = []
        if 'No demands were found' not in align_output and align_output.strip():
            try:
                align_jobs = json.loads(align_output)
                if isinstance(align_jobs, list):
                    for job in align_jobs:
                        # Get metadata from database
                        try:
                            metadata = Metadata.objects.get(fastq_name=job.get('load_name'))
                            metadata_dict = {
                                'organism': metadata.organism_common_name,
                                'batch': metadata.batch_name_from_vendor,
                                'workflow': determine_workflow(metadata.batch_name_from_vendor)
                            }
                        except Metadata.DoesNotExist:
                            metadata_dict = {
                                'organism': 'N/A',
                                'batch': 'N/A',
                                'workflow': 'N/A'
                            }
                        
                        alignment_queue.append({
                            'fastq_name': job.get('load_name'),
                            'demand_id': job.get('demand_id'),
                            'status': job.get('status'),
                            'workflow': metadata_dict['workflow'],
                            'added_time': job.get('created_at'),
                            'start_time': job.get('started_at'),
                            'metadata': metadata_dict
                        })
            except json.JSONDecodeError:
                logger.error(f"Failed to parse alignment queue data: {align_output}")
        
        # Process post-align queue
        postqc_queue = []
        if 'No demands were found' not in post_align_output and post_align_output.strip():
            try:
                post_align_jobs = json.loads(post_align_output)
                if isinstance(post_align_jobs, list):
                    for job in post_align_jobs:
                        # Get metadata from database
                        try:
                            metadata = Metadata.objects.get(fastq_name=job.get('load_name'))
                            metadata_dict = {
                                'organism': metadata.organism_common_name,
                                'batch': metadata.batch_name_from_vendor,
                                'workflow': determine_workflow(metadata.batch_name_from_vendor)
                            }
                        except Metadata.DoesNotExist:
                            metadata_dict = {
                                'organism': 'N/A',
                                'batch': 'N/A',
                                'workflow': 'N/A'
                            }
                        
                        postqc_queue.append({
                            'fastq_name': job.get('load_name'),
                            'demand_id': job.get('demand_id'),
                            'status': job.get('status'),
                            'workflow': metadata_dict['workflow'],
                            'added_time': job.get('created_at'),
                            'start_time': job.get('started_at'),
                            'metadata': metadata_dict
                        })
            except json.JSONDecodeError:
                logger.error(f"Failed to parse post-align queue data: {post_align_output}")
        
        return {
            'status': 'success',
            'alignment_queue': alignment_queue,
            'postqc_queue': postqc_queue
        }
    
    except Exception as e:
        logger.error(f"Error getting queue data: {str(e)}")
        return {
            'status': 'error',
            'message': f'Failed to get queue data: {str(e)}',
            'alignment_queue': [],
            'postqc_queue': []
        } 