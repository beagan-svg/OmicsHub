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
from viewer.models import Alignment, PostQC, Metadata, Main

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
        output = subprocess.check_output([script_path], stderr=subprocess.STDOUT, universal_newlines=True)
        return output
    except subprocess.CalledProcessError as e:
        logger.error(f"Script execution failed: {e.output}")
        return e.output

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

def determine_workflow(batch_name):
    """
    Determine workflow type (MTX/RTX) based on batch name.
    
    Args:
        batch_name (str): The batch name from vendor
        
    Returns:
        str: 'MTX' or 'RTX' workflow type
    """
    if not batch_name:
        return 'RTX'  # Default to RTX if no batch name
        
    batch_name_upper = batch_name.upper()
    
    if batch_name_upper.startswith('MTX') or 'ATX' in batch_name_upper:
        return 'MTX'
    elif batch_name_upper.startswith('RTX'):
        return 'RTX'
    else:
        return 'RTX'  # Default to RTX for unrecognized patterns

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

def generate_alignment_command(sample_data, config=None):
    """
    Generate the OCS alignment command based on sample data.
    
    Args:
        sample_data (dict): Sample metadata including organism, load_name, etc.
        config (dict, optional): Pipeline configuration with references
        
    Returns:
        dict: Command details including full_command, workflow, etc.
    """
    # Get basic sample info
    organism = sample_data.get('organism_common_name', '')
    load_name = sample_data.get('load_name', '')
    batch_name = sample_data.get('batch_name_from_vendor', '')
    library_prep = sample_data.get('library_prep', '')
    
    # Determine workflow
    workflow = determine_workflow(batch_name)
    
    # Get reference based on organism
    if not config:
        config = load_pipeline_config()
        
    reference_map = {
        'mouse': 'mouse_10x_mm10_genome_star2.7.1a',
        'human': 'human_10x_grch38_genome_star2.7.1a',
        # Add more organism mappings as needed
    }
    
    # Try to get from config first, then fallback to hardcoded defaults
    references = config.get('references', {})
    reference = None
    
    # Try exact match first
    for ref_id, ref_info in references.items():
        if isinstance(ref_info, dict) and ref_info.get('organism', '').lower() == organism.lower():
            reference = ref_id
            break
    
    # If no match in config, use hardcoded defaults
    if not reference:
        reference = reference_map.get(organism.lower(), 'human_10x_grch38_genome_star2.7.1a')
    
    # Set chemistry version (default to v3)
    chemistry = sample_data.get('chemistry', 'v3')
    
    # Build the command based on workflow
    if workflow == 'MTX':
        command = (
            f'ocs fastqs align tenx-arc '
            f'--reference-names "{reference}" '
            f'--asset-name cellranger-arc '
            f'--load-names "{load_name}" '
            f'--notify-on FAILED '
            f'--notify beagan.nguy@alleninstitute.org'
        )
    else:  # RTX
        command = (
            f'ocs fastqs align tenx-rnaseq '
            f'--reference-names "{reference}" '
            f'--asset-name cellranger-rnaseq '
            f'--load-names "{load_name}" '
            f'--cellranger-addopts "--chemistry {chemistry} --include-introns"'
        )
    
    # Wrap command in bash script
    full_command = (
        '#!/bin/bash\n'
        'source /home/svc_bicore/genomics-cloud-services/gcs-cli/.venv/bin/activate\n'
        'export AWS_PROFILE=aibs-bicore\n'
        f'{command}'
    )
    
    return {
        'command': command,
        'full_command': full_command,
        'workflow': workflow,
        'reference': reference,
        'chemistry': chemistry
    }

def submit_sample_for_alignment(sample, config=None):
    """
    Submit a sample for alignment processing.
    
    Args:
        sample (dict): Sample metadata
        config (dict, optional): Pipeline configuration
        
    Returns:
        dict: Result of submission including status and demand_id
    """
    from django.utils import timezone
    from viewer.models import SampleQueue, Main, Alignment
    import subprocess
    import json
    import time
    import uuid
    
    # Check ingest status
    if sample.get('ingest_status') != 'Completed':
        return {
            'fastq_name': sample.get('fastq_name'),
            'status': 'error',
            'message': 'Ingest not completed'
        }
    
    # Check job capacity
    job_counts = count_running_jobs()
    if job_counts['total'] >= 100:
        return {
            'fastq_name': sample.get('fastq_name'),
            'status': 'error',
            'message': 'Maximum job capacity reached (100 jobs)'
        }
    
    try:
        # Generate command
        command_details = generate_alignment_command(sample, config)
        
        # Add sample to server-side queue
        queue_entry = SampleQueue(
            fastq_name=sample.get('fastq_name'),
            queue_type='alignment',
            workflow=command_details['workflow'],
            command=command_details['full_command'],
            status='pending',
            metadata=json.dumps(sample),
            added_time=timezone.now()
        )
        queue_entry.save()
        
        # Execute the command (wrapped script)
        temp_script = f"/tmp/pipeline_submit_{uuid.uuid4().hex}.sh"
        with open(temp_script, 'w') as f:
            f.write(command_details['full_command'])
        
        subprocess.run(['chmod', '+x', temp_script])
        result = subprocess.run([temp_script], capture_output=True, text=True)
        
        # Parse output for demand_id
        demand_id = None
        output = result.stdout
        
        for line in output.splitlines():
            if "demand_id" in line:
                try:
                    demand_data = json.loads(line)
                    demand_id = demand_data.get("demand_id")
                except json.JSONDecodeError:
                    # Try to extract demand_id using string parsing
                    import re
                    match = re.search(r'"demand_id"\s*:\s*"([^"]+)"', line)
                    if match:
                        demand_id = match.group(1)
        
        # Clean up temp script
        subprocess.run(['rm', temp_script])
        
        if demand_id:
            # Update queue entry
            queue_entry.demand_id = demand_id
            queue_entry.status = 'submitted'
            queue_entry.start_time = timezone.now()
            queue_entry.save()
            
            # Create or update alignment record
            alignment, created = Alignment.objects.get_or_create(
                fastq_name_id=sample.get('fastq_name'),
                defaults={
                    'demand_id': demand_id,
                    'status_id': 'SUBMITTED',
                    'start_time': timezone.now(),
                    'end_time': None,
                    'retry_count': 0
                }
            )
            
            if not created:
                alignment.demand_id = demand_id
                alignment.status_id = 'SUBMITTED'
                alignment.start_time = timezone.now()
                alignment.end_time = None
                alignment.save()
            
            # Update Main record
            try:
                main = Main.objects.get(fastq_name=sample.get('fastq_name'))
                main.alignment_status = 'In Progress'
                main.save()
            except Main.DoesNotExist:
                pass
            
            return {
                'fastq_name': sample.get('fastq_name'),
                'status': 'success',
                'demand_id': demand_id,
                'workflow': command_details['workflow'],
                'message': f'Submitted successfully with demand_id: {demand_id}'
            }
        else:
            # Mark as failed in queue
            queue_entry.status = 'failed'
            queue_entry.save()
            
            return {
                'fastq_name': sample.get('fastq_name'),
                'status': 'error',
                'message': f'Failed to get demand_id from submission output: {output}'
            }
            
    except Exception as e:
        return {
            'fastq_name': sample.get('fastq_name'),
            'status': 'error',
            'message': str(e)
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
    """
    Get data from the server-side alignment and post-QC queues.
    
    Returns:
        dict: Queue data for alignment and post-QC
    """
    from viewer.models import SampleQueue
    
    # Get alignment queue items
    alignment_queue = SampleQueue.objects.filter(
        queue_type='alignment', 
        status__in=['pending', 'submitted', 'running']
    ).order_by('-added_time')
    
    # Get post-QC queue items
    postqc_queue = SampleQueue.objects.filter(
        queue_type='postqc', 
        status__in=['pending', 'submitted', 'running']
    ).order_by('-added_time')
    
    # Format data for frontend
    alignment_data = [{
        'fastq_name': item.fastq_name,
        'workflow': item.workflow,
        'demand_id': item.demand_id,
        'status': item.status,
        'added_time': item.added_time,
        'start_time': item.start_time,
        'metadata': item.metadata
    } for item in alignment_queue]
    
    postqc_data = [{
        'fastq_name': item.fastq_name,
        'workflow': item.workflow,
        'demand_id': item.demand_id,
        'status': item.status,
        'added_time': item.added_time,
        'start_time': item.start_time,
        'metadata': item.metadata
    } for item in postqc_queue]
    
    return {
        'alignment_queue': alignment_data,
        'postqc_queue': postqc_data
    } 