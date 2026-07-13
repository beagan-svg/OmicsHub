from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.core.cache import cache
from ocs.pipeline_utils import count_running_jobs
from ocs.models import RunningJob, CompletedJob
from ocs.serializers import serialize_running_jobs, serialize_completed_jobs

class JobMonitorView(LoginRequiredMixin, TemplateView):
    """
    View for monitoring job status.
    
    This view handles:
    - Job status updates
    - Real-time monitoring
    - Job history
    """
    template_name = 'ocs/pipeline/job_monitor.html'
    
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
        """Get fresh job data using the job tracking models."""
        return {
            'job_counts': count_running_jobs(),
            'running_jobs': serialize_running_jobs(RunningJob.objects.all()),
            'completed_jobs': serialize_completed_jobs(
                CompletedJob.objects.order_by('-alignment_end_time', '-postqc_end_time')[:50]
            ),
        }

class QueueManagementView(LoginRequiredMixin, TemplateView):
    """
    View for managing job queues.
    
    This view handles:
    - Queue viewing
    - Queue management
    - Queue item actions
    """
    template_name = 'ocs/pipeline/queue_management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Queue Management'
        return context 