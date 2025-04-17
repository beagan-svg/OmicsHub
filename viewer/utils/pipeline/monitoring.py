"""
Pipeline job monitoring utilities.
"""
import json
import logging
from django.utils import timezone
from datetime import datetime
from .commands import create_bash_script, run_bash_script
from viewer.models import Alignment, PostQC, Main

# Set up logging
logger = logging.getLogger(__name__)

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