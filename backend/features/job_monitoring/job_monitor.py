from django.views.generic import TemplateView
from django.http import JsonResponse
from django.core.cache import cache
from django.db import connection
from backend.utils.pipeline_utils import count_running_jobs, update_all_running_jobs
from backend.core.models import Alignment, RunningJob, CompletedJob, FailedJob, Metadata

class JobMonitorView(TemplateView):
    """
    View for monitoring job status.
    
    This view handles:
    - Job status updates
    - Real-time monitoring
    - Job history
    """
    template_name = 'viewer/pipeline/job_monitor.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Job Monitor'
        
        # Get user ID for cache
        user_id = getattr(self.request.user, 'id', 'anonymous')
        cache_key = f'job_monitor_data_{user_id}'
        
        # Try to get from cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            context.update(cached_data)
        else:
            # Get fresh data
            fresh_data = self._get_fresh_job_data()
            cache.set(cache_key, fresh_data, timeout=300)  # 5 minute cache
            context.update(fresh_data)
            
        return context

    def _get_fresh_job_data(self):
        """Get fresh job data using the new job tracking models."""
        # Get actual running job counts from OCS
        job_counts = count_running_jobs()
        
        # Get running jobs from RunningJob table
        running_jobs_data = RunningJob.objects.all()
        
        # Format running jobs for display
        running_jobs_formatted = []
        for job in running_jobs_data:
            # Get metadata for display
            try:
                metadata = Metadata.objects.get(fastq_name=job.fastq_name)
                organism = metadata.organism_common_name
                batch = metadata.batch_name_from_vendor
            except Metadata.DoesNotExist:
                organism = 'Unknown'
                batch = 'Unknown'
            
            # Add alignment job if exists
            if job.alignment_demand_id:
                running_jobs_formatted.append({
                    'fastq_name': job.fastq_name,
                    'command': job.alignment_command or '',
                    'demand_id': job.alignment_demand_id,
                    'attempts': job.alignment_attempts,
                    'time': job.time.isoformat() if job.time else None,
                    'organism': organism,
                    'batch': batch,
                    'workflow': 'MTX' if 'MTX' in batch else 'RTX',
                    'job_type': 'alignment'
                })
            
            # Add post-QC job if exists
            if job.postqc_demand_id:
                running_jobs_formatted.append({
                    'fastq_name': job.fastq_name,
                    'command': job.postqc_command or '',
                    'demand_id': job.postqc_demand_id,
                    'attempts': job.postqc_attempts,
                    'time': job.time.isoformat() if job.time else None,
                    'organism': organism,
                    'batch': batch,
                    'workflow': 'MTX' if 'MTX' in batch else 'RTX',
                    'job_type': 'post-QC'
                })
        
        # Get completed jobs from CompletedJob table (last 50) - SIMPLIFIED
        # Use select_related to avoid N+1 queries and get all data in one go
        completed_jobs_queryset = CompletedJob.objects.select_related().all().order_by('-alignment_end_time', '-postqc_end_time')[:50]
        
        # Get all metadata for these jobs in a single query
        fastq_names = [job.fastq_name for job in completed_jobs_queryset]
        metadata_dict = {
            metadata.fastq_name: metadata 
            for metadata in Metadata.objects.filter(fastq_name__in=fastq_names)
        }
        
        # Format completed jobs - just return raw data, let frontend process it
        completed_jobs_formatted = []
        for job in completed_jobs_queryset:
            # Get metadata from our pre-fetched dict
            metadata = metadata_dict.get(job.fastq_name)
            
            # Just return the raw data with minimal processing
            job_data = {
                'fastq_name': job.fastq_name,
                'alignment_demand_id': job.alignment_demand_id,
                'alignment_status': job.alignment_status,
                'alignment_start_time': job.alignment_start_time.isoformat() if job.alignment_start_time else None,
                'alignment_end_time': job.alignment_end_time.isoformat() if job.alignment_end_time else None,
                'alignment_attempts': job.alignment_attempts or 0,
                'alignment_command': job.alignment_command,
                'postqc_demand_id': job.postqc_demand_id,
                'postqc_status': job.postqc_status,
                'postqc_start_time': job.postqc_start_time.isoformat() if job.postqc_start_time else None,
                'postqc_end_time': job.postqc_end_time.isoformat() if job.postqc_end_time else None,
                'postqc_attempts': job.postqc_attempts or 0,
                'postqc_command': job.postqc_command,
            }
            
            # Add metadata if available
            if metadata:
                job_data['organism_common_name'] = metadata.organism_common_name
                job_data['batch_name_from_vendor'] = metadata.batch_name_from_vendor
            else:
                job_data['organism_common_name'] = 'Unknown'
                job_data['batch_name_from_vendor'] = 'Unknown'
            
            completed_jobs_formatted.append(job_data)
        
        return {
            'job_counts': job_counts,
            'running_jobs': running_jobs_formatted,
            'completed_jobs': completed_jobs_formatted
        }

class QueueManagementView(TemplateView):
    """
    View for managing job queues.
    
    This view handles:
    - Queue viewing
    - Queue management
    - Queue item actions
    """
    template_name = 'viewer/pipeline/queue_management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Queue Management'
        return context 