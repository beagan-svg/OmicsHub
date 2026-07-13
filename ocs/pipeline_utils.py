import json
import os
import subprocess
import tempfile
import yaml
import logging
from pathlib import Path
from datetime import datetime
from django.conf import settings
from ocs.models import Alignment, PostQC, Main, RunningJob
from django.db import transaction

# Set up logging
logger = logging.getLogger(__name__)

# Terminal OCS demand statuses (job leaves running_jobs once it reaches one).
TERMINAL_STATUSES = ('COMPLETED', 'FAILED', 'ABORTED')

# Map an OCS status to the human label stored on the Main table.
MAIN_STATUS_LABELS = {
    'COMPLETED': 'Completed',
    'FAILED': 'Failed',
    'ABORTED': 'Aborted',
}

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
        logger.warning(f"Pipeline config file not found: {PIPELINE_CONFIG_PATH}")
        return {}

def create_bash_script(commands, script_name='temp_script.sh'):
    """Create a temporary bash script with the given commands.

    Scripts go in a per-user temp directory so concurrent users don't collide
    on the same /tmp filename (which would fail under /tmp's sticky bit).
    """
    script_dir = Path(tempfile.gettempdir()) / f'ocs_scripts_{os.getuid()}'
    script_dir.mkdir(mode=0o700, exist_ok=True)
    script_path = script_dir / script_name

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
    """Run a bash script and return the output silently"""
    try:
        execute_commands = getattr(settings, 'EXECUTE_OCS_COMMANDS', True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # # Prepare logging directory and file
        # with open(script_path, 'r') as script_file:
        #     script_content = script_file.read()
        # log_dir = Path('pipeline_command_logs')
        # log_dir.mkdir(exist_ok=True)
        # log_path = log_dir / f'command_log_{timestamp}.txt'
        #
        # # Log command and execution mode
        # with open(log_path, 'w') as log_file:
        #     log_file.write(f"--- COMMAND LOG AT {datetime.now().isoformat()} ---\n")
        #     log_file.write(f"Script path: {script_path}\n")
        #     log_file.write(f"Execute commands setting: {execute_commands}\n\n")
        #     log_file.write("Script content:\n")
        #     log_file.write(script_content)
        #     log_file.write("\n\n")
        #     if not execute_commands:
        #         log_file.write("--- COMMAND EXECUTION DISABLED (TEST MODE) ---\n")

        if not execute_commands:
            mock_response = json.dumps({
                "demand_status": "SUBMITTED", 
                "demand_id": f"test-demand-{timestamp}"
            })
            # with open(log_path, 'a') as log_file:
            #     log_file.write(f"\n--- MOCK RESPONSE (TEST MODE) ---\n{mock_response}\n--- END OF COMMAND LOG ---\n")
            return mock_response

        # Execute the script
        output = subprocess.check_output([script_path], stderr=subprocess.STDOUT, universal_newlines=True)

        # # Append output to log
        # with open(log_path, 'a') as log_file:
        #     log_file.write(f"\n--- COMMAND OUTPUT ---\n{output}\n--- END OF COMMAND LOG ---\n")

        return output

    except subprocess.CalledProcessError as e:
        logger.error(f"Script execution failed: {e.output}")
        return e.output
    except Exception as e:
        logger.error(f"Error with script: {str(e)}")
        return f"Error: {str(e)}"

def count_running_jobs():
    """Count the number of running alignment and post-align jobs from OCS"""
    align_count = 0
    post_align_count = 0
    
    logger.info("=== Starting job count process ===")
    
    # Check alignment jobs
    script_path = create_bash_script(
        'ocs core gwo demand list-demands --demand-type align --status IN_PROGRESS --format json',
        'check_align_jobs.sh'
    )
    logger.debug(f"Executing alignment count script: {script_path}")
    output = run_bash_script(script_path)
    logger.debug(f"Raw alignment output: {output}")
    
    try:
        if 'No demands were found' not in output and output.strip():
            align_jobs = json.loads(output)
            if isinstance(align_jobs, list):
                align_count = len(align_jobs)
                logger.info(f"Found {align_count} running alignment jobs in OCS")
                logger.debug(f"Alignment jobs details: {json.dumps(align_jobs, indent=2)}")
            else:
                logger.error(f"Unexpected alignment jobs output format: {output}")
        else:
            logger.info("No running alignment jobs found")
    except json.JSONDecodeError:
        logger.error(f"Failed to parse alignment jobs output: {output}")
    except Exception as e:
        logger.error(f"Error counting alignment jobs: {str(e)}")
    
    # Check post-alignment jobs
    script_path = create_bash_script(
        'ocs core gwo demand list-demands --demand-type post-align --status IN_PROGRESS --format json',
        'check_post_align_jobs.sh'
    )
    logger.debug(f"Executing post-alignment count script: {script_path}")
    output = run_bash_script(script_path)
    logger.debug(f"Raw post-alignment output: {output}")
    
    try:
        if 'No demands were found' not in output and output.strip():
            post_align_jobs = json.loads(output)
            if isinstance(post_align_jobs, list):
                post_align_count = len(post_align_jobs)
                logger.info(f"Found {post_align_count} running post-alignment jobs in OCS")
                logger.debug(f"Post-alignment jobs details: {json.dumps(post_align_jobs, indent=2)}")
            else:
                logger.error(f"Unexpected post-alignment jobs output format: {output}")
        else:
            logger.info("No running post-alignment jobs found")
    except json.JSONDecodeError:
        logger.error(f"Failed to parse post-alignment jobs output: {output}")
    except Exception as e:
        logger.error(f"Error counting post-alignment jobs: {str(e)}")
    
    total = align_count + post_align_count
    logger.info(f"=== Job count summary ===")
    logger.info(f"Alignment jobs: {align_count}")
    logger.info(f"Post-alignment jobs: {post_align_count}")
    logger.info(f"Total running jobs: {total}")
    
    return {
        'align_count': align_count,
        'post_align_count': post_align_count,
        'total': total
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
    logger.warning(f"No reference found for organism: {organism_common_name}")
    return ''

def get_chemistry(library_prep_method):
    """Get chemistry value for a library prep method"""
    config = load_pipeline_config()
    chemistries = config.get('chemistries', {})
    
    # Try direct lookup
    if library_prep_method in chemistries:
        return chemistries[library_prep_method]
    
    # Default to SC3Pv3 if no match
    logger.warning(f"No chemistry found for library prep: {library_prep_method}")
    return ''

def create_submission_command(workflow_type, job_type, sample_data, notification_email, config=None):
    """
    Create a submission command based on workflow type, job type, and sample data.
    
    This function dynamically generates commands by parsing the workflows section
    of the pipeline configuration YAML file.
    
    Args:
        workflow_type (str): 'mtx' or 'rtx'
        job_type (str): 'alignment' or 'postqc'
        sample_data (dict): Dictionary containing sample information with keys:
            - organism_common_name: str
            - load_name: str
            - library_prep: str (for RTX workflows)
            - batch_name_from_vendor: str (optional, for workflow determination)
        notification_email (str): Email address for job notifications
        config (dict, optional): Pipeline configuration. If None, will load from file.
    
    Returns:
        str or False: The command template with parameters filled in, or False if no matching configuration found
    
    Raises:
        ValueError: If workflow/job type not found in configuration
    """
    
    # Load config if not provided
    if config is None:
        config = load_pipeline_config()
    
    # Get workflows section
    workflows = config.get('workflows', {})
    
    if workflow_type not in workflows:
        raise ValueError(f"Workflow type '{workflow_type}' not found in configuration")
    
    workflow = workflows[workflow_type]
    
    if job_type not in workflow:
        raise ValueError(f"Job type '{job_type}' not found for workflow '{workflow_type}'")
    
    job_config = workflow[job_type]
    
    # Get reference and chemistry
    reference = get_reference_name(sample_data.get('organism_common_name', ''))
    chemistry = get_chemistry(sample_data.get('library_prep', ''))
    
    # For MTX workflows, the structure is simpler
    if workflow_type == 'mtx':
        command_template = job_config.get('command_template', '')
        
        if not command_template:
            raise ValueError(f"No command template found for {workflow_type} {job_type}")
        
        # Fill in template parameters
        command = command_template.format(
            reference=reference,
            load_name=sample_data.get('load_name', ''),
            notification_email=notification_email
        )
        
        return command
    
    # For RTX workflows, we need to match library prep method
    elif workflow_type == 'rtx':
        library_prep = sample_data.get('library_prep', '')
        
        # Find matching library prep pattern
        matched_config = None
        for pattern, pattern_config in job_config.items():
            if isinstance(pattern_config, dict) and 'command_template' in pattern_config:
                # Check if library prep matches any of the patterns
                if '|' in pattern:
                    # Multiple patterns separated by |
                    patterns = pattern.split('|')
                    if library_prep in patterns:
                        matched_config = pattern_config
                        break
                else:
                    # Single pattern
                    if library_prep == pattern:
                        matched_config = pattern_config
                        break
        
        if matched_config is None:
            # No matching pattern found - return False instead of fallback
            logger.warning(f"Library prep method '{library_prep}' not found in configuration for {workflow_type} {job_type}")
            return False
        
        command_template = matched_config.get('command_template', '')
        
        if not command_template:
            raise ValueError(f"No command template found for {workflow_type} {job_type} with library prep {library_prep}")
        
        # Fill in template parameters
        command = command_template.format(
            reference=reference,
            load_name=sample_data.get('load_name', ''),
            chemistry=chemistry,
            notification_email=notification_email
        )
        
        return command
    
    else:
        raise ValueError(f"Unknown workflow type: {workflow_type}")

def stop_alignment_job(demand_id):
    """Stop an alignment job"""
    command = f'ocs core gwo demand stop --demand-id {demand_id} --format json'
    script_path = create_bash_script(command, f'stop_job_{demand_id}.sh')
    output = run_bash_script(script_path)
    
    # Check if job was stopped successfully
    check_result = process_job_status_update(demand_id)
    
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

def move_jobs(fastq_name, demand_id, status, demand_type, start_time=None, end_time=None):
    """
    Move a job from running_jobs to completed_jobs or failed_jobs based on status

    Args:
        fastq_name (str): The name of the FASTQ file
        demand_id (str): The demand ID of the job
        status (str): The status of the job (COMPLETED, FAILED, ABORTED)
        demand_type (str): The type of demand (align or post-align)
        start_time (datetime, optional): The start time of the job. Defaults to None.
        end_time (datetime, optional): The end time of the job. Defaults to None.
    """
    logger.info(f"Moving job {fastq_name} (demand_id: {demand_id}, type: {demand_type}) to appropriate table with status: {status}")
    
    try:
        from ocs.models import RunningJob, CompletedJob, FailedJob, QueueJobs
        from django.db import transaction
        
        # Find the running job with a single query
        logger.debug(f"Looking for running job with demand_type: {demand_type}, demand_id: {demand_id}")
        if demand_type == 'align':
            running_job = RunningJob.objects.filter(alignment_demand_id=demand_id).first()
        else:  # post-align
            running_job = RunningJob.objects.filter(postqc_demand_id=demand_id).first()
        
        if not running_job:
            logger.warning(f"No running job found for demand_id {demand_id} of type {demand_type}")
            # Check if there are any running jobs for this fastq_name
            all_running_jobs = RunningJob.objects.filter(fastq_name=fastq_name)
            logger.debug(f"Found {all_running_jobs.count()} running jobs for fastq_name {fastq_name}")
            for job in all_running_jobs:
                logger.debug(f"  - alignment_demand_id: {job.alignment_demand_id}, postqc_demand_id: {job.postqc_demand_id}")
            return False
            
        logger.debug(f"Found running job: {running_job.fastq_name} (alignment_demand_id: {running_job.alignment_demand_id}, postqc_demand_id: {running_job.postqc_demand_id})")
        
        # Use transaction to ensure atomicity
        with transaction.atomic():
            # If job failed or was aborted, move to failed_jobs
            if status in ('FAILED', 'ABORTED'):
                logger.info(f"Job status is {status}, moving to failed_jobs")
                
                failed_job = FailedJob.objects.create(
                    fastq_name=running_job.fastq_name,
                    alignment_command=running_job.alignment_command,
                    postqc_command=running_job.postqc_command,
                    time=running_job.time,
                    alignment_attempts=running_job.alignment_attempts,
                    postqc_attempts=running_job.postqc_attempts,
                    alignment_demand_id=running_job.alignment_demand_id if demand_type == 'align' else None,
                    postqc_demand_id=running_job.postqc_demand_id if demand_type == 'post-align' else None
                )
                
                logger.info(f"Created failed job record for {fastq_name} with primary key: {failed_job.fastq_name}")
            else:
                # Job completed successfully, move to completed_jobs
                logger.info(f"Job status is {status}, moving to completed_jobs")
                
                # Check if a completed job record already exists for this fastq_name
                existing_completed_job = CompletedJob.objects.filter(fastq_name=fastq_name).first()
                
                if existing_completed_job:
                    logger.info(f"Found existing completed job record for {fastq_name}, updating with {demand_type} information")
                    
                    # Update the existing record with new information
                    if demand_type == 'align':
                        # Update alignment-specific fields
                        existing_completed_job.alignment_command = running_job.alignment_command
                        existing_completed_job.alignment_attempts = running_job.alignment_attempts
                        existing_completed_job.alignment_demand_id = running_job.alignment_demand_id
                        existing_completed_job.alignment_status = status
                        existing_completed_job.alignment_start_time = start_time
                        existing_completed_job.alignment_end_time = end_time
                    else:  # post-align
                        # Update post-QC specific fields
                        existing_completed_job.postqc_command = running_job.postqc_command
                        existing_completed_job.postqc_attempts = running_job.postqc_attempts
                        existing_completed_job.postqc_demand_id = running_job.postqc_demand_id
                        existing_completed_job.postqc_status = status
                        existing_completed_job.postqc_start_time = start_time
                        existing_completed_job.postqc_end_time = end_time
                    
                    existing_completed_job.save()
                    logger.info(f"Updated existing completed job record for {fastq_name}")
                    
                else:
                    logger.info(f"No existing completed job record for {fastq_name}, creating new one")
                    
                    # Build completed job data for new record
                    completed_job_data = {
                        'fastq_name': running_job.fastq_name,
                        'alignment_command': running_job.alignment_command,
                        'postqc_command': running_job.postqc_command,
                        'alignment_attempts': running_job.alignment_attempts,
                        'postqc_attempts': running_job.postqc_attempts,
                        'alignment_demand_id': running_job.alignment_demand_id,
                        'postqc_demand_id': running_job.postqc_demand_id
                    }
                    
                    # Add type-specific fields
                    if demand_type == 'align':
                        completed_job_data.update({
                            'alignment_status': status,
                            'alignment_start_time': start_time,
                            'alignment_end_time': end_time,
                        })
                    else:  # post-align
                        completed_job_data.update({
                            'postqc_status': status,
                            'postqc_start_time': start_time,
                            'postqc_end_time': end_time,
                        })
                    
                    # Create completed job record
                    completed_job = CompletedJob.objects.create(**completed_job_data)
                    logger.info(f"Created completed job record for {fastq_name} with primary key: {completed_job.fastq_name}")
                
                # AUTO-UPDATE PENDING POST-QC JOBS TO READY
                # If an alignment job completed successfully, check for pending post-QC jobs
                if demand_type == 'align' and status == 'COMPLETED':
                    logger.info(f"Alignment job completed successfully for {fastq_name}, checking for pending post-QC jobs in queue")
                    try:
                        # Find queue entries for this fastq_name that have post-QC commands and are pending
                        pending_postqc_jobs = QueueJobs.objects.filter(
                            fastq_name=fastq_name,
                            postqc_command__isnull=False,
                            postqc_command__gt='',  # Not empty
                            status__in=['Pending', 'pending', 'PENDING']
                        )
                        
                        updated_count = 0
                        for queue_job in pending_postqc_jobs:
                            old_status = queue_job.status
                            queue_job.status = 'Ready'
                            queue_job.save()
                            updated_count += 1
                            logger.info(f"Updated queue job for {fastq_name}: {old_status} -> Ready (post-QC command ready to process)")
                        
                        if updated_count > 0:
                            logger.info(f"Successfully updated {updated_count} pending post-QC jobs to Ready status for {fastq_name}")
                        else:
                            logger.debug(f"No pending post-QC jobs found in queue for {fastq_name}")
                            
                    except Exception as queue_update_error:
                        # Log the error but don't fail the overall job move operation
                        logger.error(f"Error updating pending post-QC jobs to Ready for {fastq_name}: {queue_update_error}")
            
            # Delete running job record
            logger.debug(f"Deleting running job record for {fastq_name} (primary key: {running_job.fastq_name})")
            running_job.delete()
            logger.info(f"Deleted running job record for {fastq_name}")
        
        return True
            
    except Exception as e:
        logger.exception(f"Error moving job to appropriate table: {str(e)}")
        return False

def get_latest_result_time(fastq_name, target_type):
    """
    Helper function to get the latest `last_update_time` for a given demand_type
    """
    try:
        command = f'ocs fastqs list results --fastq-name {fastq_name} --format json'
        script_path = create_bash_script(command, f'check_results_{fastq_name}.sh')
        output = run_bash_script(script_path)
        
        if not output or not output.strip():
            logger.warning(f"Empty output when checking results for {fastq_name}")
            return None
            
        results_json = json.loads(output)
        
        if not results_json:
            logger.warning(f"No results found for {fastq_name}")
            return None

        latest_time = None
        for sample in results_json:
            for result_group in sample.get("fastq_results", []):
                for result in result_group.get("result", []):
                    if result.get("demand_type") == target_type:
                        ts = result.get("last_update_time")
                        if ts and (not latest_time or ts > latest_time):
                            latest_time = ts
        
        if not latest_time:
            logger.warning(f"No {target_type} results found for {fastq_name}")
            
        return latest_time
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse results JSON for {fastq_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting latest result time for {fastq_name}: {e}")
        return None

def apply_job_status(running_job, demand_id, demand_type, job_status, start_time):
    """Apply one demand's status to the Alignment/PostQC and Main tables.

    Terminal statuses (COMPLETED/FAILED/ABORTED) also move the job out of
    running_jobs via move_jobs(); IN_PROGRESS only refreshes the status fields.
    """
    fastq_name = running_job.fastq_name

    if job_status in TERMINAL_STATUSES:
        logger.info(f"Job {demand_id} has terminal status: {job_status}")
        end_time = get_latest_result_time(fastq_name, demand_type) if job_status == 'COMPLETED' else None

        with transaction.atomic():
            if demand_type == 'align':
                Alignment.objects.filter(fastq_name_id=fastq_name).update(
                    status_id=job_status,
                    start_time=start_time,
                    end_time=end_time,
                    retry_count=running_job.alignment_attempts,
                )
                Main.objects.filter(fastq_name_id=fastq_name).update(alignment_status=job_status)
            elif demand_type == 'post-align':
                PostQC.objects.filter(fastq_name_id=fastq_name).update(
                    status_id=job_status,
                    start_time=start_time,
                    end_time=end_time,
                    retry_count=running_job.postqc_attempts,
                )
                Main.objects.filter(fastq_name=fastq_name).update(postqc_status=job_status)

            if not move_jobs(fastq_name=fastq_name, demand_id=demand_id, status=job_status,
                             demand_type=demand_type, start_time=start_time, end_time=end_time):
                # Status updates already succeeded, so don't raise — just record it.
                logger.error(f"Failed to move job {fastq_name} (demand_id: {demand_id}) to terminal table")

    elif job_status == 'IN_PROGRESS':
        if demand_type == 'align':
            Alignment.objects.filter(fastq_name_id=fastq_name).update(status_id=job_status)
            Main.objects.filter(fastq_name=fastq_name).update(alignment_status=job_status)
        elif demand_type == 'post-align':
            PostQC.objects.filter(fastq_name_id=fastq_name).update(status_id=job_status)
            Main.objects.filter(fastq_name=fastq_name).update(postqc_status=job_status)
    else:
        logger.warning(f"Unknown job status '{job_status}' for demand_id {demand_id}")


def process_job_status_update(demand_id):
    """Fetch one demand's status from OCS and apply it to the database."""
    try:
        command = f'ocs core gwo demand get-status --demand-id {demand_id} --format json'
        script_path = create_bash_script(command, f'check_status_{demand_id}.sh')
        output = run_bash_script(script_path)
        status_json = json.loads(output)

        if not status_json:
            raise ValueError("Empty response from get-status command")

        status_data = status_json[0]
        job_status = status_data.get('status', '')
        start_time = status_data.get('start_time', '')
        demand_type = status_data.get('demand_type', '')

        if demand_type == 'align':
            running_job = RunningJob.objects.filter(alignment_demand_id=demand_id).first()
        elif demand_type == 'post-align':
            running_job = RunningJob.objects.filter(postqc_demand_id=demand_id).first()
        else:
            raise ValueError(f"Unknown demand_type '{demand_type}' for demand_id {demand_id}")

        if not running_job:
            raise ValueError(f"No running job found for demand_id {demand_id} of type {demand_type}")

        apply_job_status(running_job, demand_id, demand_type, job_status, start_time)

        return {
            'status': 'success',
            'demand_id': demand_id,
            'job_status': job_status,
            'start_time': start_time,
            'demand_type': demand_type,
        }

    except Exception as e:
        logger.error(f"Error processing demand_id {demand_id}: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': str(e),
            'demand_id': demand_id
        }

def update_all_running_jobs():
    """Update status of all running jobs in the database using bulk status check"""
    results = []
    
    # Get all jobs from running_jobs table
    db_running_jobs = RunningJob.objects.all()
    logger.info(f"Found {len(db_running_jobs)} jobs in running_jobs table to check")
    
    if not db_running_jobs:
        logger.info("No running jobs found to update")
        return results
    
    # Step 1: Collect all demand_ids and create mapping
    demand_id_to_job_map = {}  # demand_id -> (job_object, job_type)
    demand_ids = []
    
    for running_job in db_running_jobs:
        # Process alignment jobs
        if running_job.alignment_demand_id:
            demand_id_to_job_map[running_job.alignment_demand_id] = (running_job, 'align')
            demand_ids.append(running_job.alignment_demand_id)
            logger.debug(f"Added alignment demand_id: {running_job.alignment_demand_id} for {running_job.fastq_name}")
        
        # Process post-QC jobs
        if running_job.postqc_demand_id:
            demand_id_to_job_map[running_job.postqc_demand_id] = (running_job, 'post-align')
            demand_ids.append(running_job.postqc_demand_id)
            logger.debug(f"Added post-QC demand_id: {running_job.postqc_demand_id} for {running_job.fastq_name}")
    
    if not demand_ids:
        logger.info("No demand_ids found to check")
        return results
    
    logger.info(f"Collected {len(demand_ids)} demand_ids for bulk status check")
    
    # Step 2: Build bulk status check command
    # Build command with multiple --demand-id flags
    demand_id_flags = []
    for demand_id in demand_ids:
        demand_id_flags.extend(['--demand-id', demand_id])
    
    command_parts = ['ocs', 'core', 'gwo', 'demand', 'get-status'] + demand_id_flags + ['--format', 'json']
    bulk_command = ' '.join(command_parts)
    
    logger.info(f"Executing bulk status check for {len(demand_ids)} demand_ids")
    logger.debug(f"Bulk command: {bulk_command}")
    
    # Step 3: Execute bulk status check
    try:
        script_path = create_bash_script(bulk_command, 'bulk_status_check.sh')
        output = run_bash_script(script_path)
        
        if not output or not output.strip():
            logger.warning("Empty output from bulk status check")
            return results
        
        # Parse JSON response
        try:
            status_responses = json.loads(output)
            if not isinstance(status_responses, list):
                logger.error(f"Expected list response, got: {type(status_responses)}")
                return results
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse bulk status JSON: {e}")
            logger.debug(f"Raw output: {output}")
            return results
        
        logger.info(f"Received status for {len(status_responses)} demand_ids")
        
        # Step 4: Process each status response
        for status_data in status_responses:
            demand_id = status_data.get('demand_id')
            job_status = status_data.get('status', '')
            start_time = status_data.get('start_time', '')
            demand_type = status_data.get('demand_type', '')
            
            if not demand_id:
                logger.warning(f"No demand_id in status response: {status_data}")
                continue
            
            # Find the corresponding job
            if demand_id not in demand_id_to_job_map:
                logger.warning(f"Received status for unknown demand_id: {demand_id}")
                continue
            
            running_job, expected_demand_type = demand_id_to_job_map[demand_id]
            fastq_name = running_job.fastq_name
            
            # Verify demand_type matches expectations
            if demand_type != expected_demand_type:
                logger.warning(f"Demand type mismatch for {demand_id}: expected {expected_demand_type}, got {demand_type}")
            
            logger.debug(f"Processing status update for {fastq_name} (demand_id: {demand_id}, type: {demand_type}, status: {job_status})")

            try:
                apply_job_status(running_job, demand_id, demand_type, job_status, start_time)

                # Add to results
                results.append({
                    'fastq_name': fastq_name,
                    'demand_id': demand_id,
                    'new_status': job_status,
                    'demand_type': demand_type
                })
                
                logger.info(f"Successfully processed status update for {fastq_name} (demand_id: {demand_id}): {job_status}")
                
            except Exception as e:
                logger.error(f"Error processing status update for demand_id {demand_id}: {e}", exc_info=True)
                # Continue processing other jobs instead of failing completely
                continue
    
    except Exception as e:
        logger.error(f"Error during bulk status check: {e}", exc_info=True)
        # Fall back to individual checks if bulk fails
        logger.info("Falling back to individual status checks...")
        for running_job in db_running_jobs:
            # Process alignment jobs
            if running_job.alignment_demand_id:
                logger.debug(f"Processing alignment job for {running_job.fastq_name} (demand_id: {running_job.alignment_demand_id})")
                
                update_result = process_job_status_update(running_job.alignment_demand_id)
                
                if update_result.get('status') == 'success':
                    logger.info(f"Successfully processed alignment job status update for {running_job.fastq_name}")
                    results.append({
                        'fastq_name': running_job.fastq_name,
                        'demand_id': running_job.alignment_demand_id,
                        'new_status': update_result.get('job_status', ''),
                        'demand_type': 'align'
                    })
                else:
                    logger.warning(f"Failed to process alignment job status update for {running_job.fastq_name}: {update_result.get('message')}")
            
            # Process post-QC jobs
            if running_job.postqc_demand_id:
                logger.debug(f"Processing post-QC job for {running_job.fastq_name} (demand_id: {running_job.postqc_demand_id})")
                
                update_result = process_job_status_update(running_job.postqc_demand_id)
                
                if update_result.get('status') == 'success':
                    logger.info(f"Successfully processed post-QC job status update for {running_job.fastq_name}")
                    results.append({
                        'fastq_name': running_job.fastq_name,
                        'demand_id': running_job.postqc_demand_id,
                        'new_status': update_result.get('job_status', ''),
                        'demand_type': 'post-align'
                    })
                else:
                    logger.warning(f"Failed to process post-QC job status update for {running_job.fastq_name}: {update_result.get('message')}")
    
    logger.info(f"Completed updating {len(results)} job statuses")
    return results
