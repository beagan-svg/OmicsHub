from django.views.generic import TemplateView
from django.http import JsonResponse
from django.core.cache import cache
from viewer.utils.pipeline_utils import count_running_jobs, update_all_running_jobs
from viewer.models import Alignment

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
        """Get fresh job data including actual running job counts from OCS."""
        # Get actual running job counts from OCS
        job_counts = count_running_jobs()
        
        # Get running jobs from OCS status
        running_jobs = []
        # We'll populate this from database but filter by demand IDs from OCS later
        alignments = Alignment.objects.filter(
            status_id__in=['SUBMITTED', 'IN_PROGRESS']
        ).select_related('fastq_name')
        
        for alignment in alignments:
            running_jobs.append({
                'fastq_name': alignment.fastq_name_id,
                'demand_id': alignment.demand_id,
                'status': alignment.status_id,
                'start_time': alignment.start_time,
                'organism': alignment.fastq_name.organism_common_name,
                'batch': alignment.fastq_name.batch_name_from_vendor,
                'workflow': 'MTX' if 'MTX' in alignment.fastq_name.batch_name_from_vendor else 'RTX'
            })
        
        # Get completed jobs
        completed_jobs = Alignment.objects.filter(
            status_id__in=['COMPLETED', 'FAILED', 'ABORTED'],
            demand_id__isnull=False
        ).exclude(
            demand_id=''
        ).order_by('-end_time')[:50].select_related('fastq_name')
        
        completed_jobs_data = [{
            'fastq_name': job.fastq_name_id,
            'demand_id': job.demand_id,
            'status': job.status_id,
            'start_time': job.start_time,
            'end_time': job.end_time,
            'organism': job.fastq_name.organism_common_name,
            'batch': job.fastq_name.batch_name_from_vendor,
            'workflow': 'MTX' if 'MTX' in job.fastq_name.batch_name_from_vendor else 'RTX',
            'duration': (job.end_time - job.start_time).total_seconds() // 60 if (job.end_time and job.start_time) else 0
        } for job in completed_jobs]
        
        return {
            'job_counts': job_counts,
            'running_jobs': running_jobs,
            'completed_jobs': completed_jobs_data
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