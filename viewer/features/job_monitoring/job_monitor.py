from django.views.generic import TemplateView
from django.http import JsonResponse

class JobMonitorView(TemplateView):
    """
    View for monitoring job status.
    
    This view handles:
    - Job status updates
    - Real-time monitoring
    - Job history
    """
    template_name = 'viewer/job_monitor.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Job Monitor'
        return context 