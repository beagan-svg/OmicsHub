from django.views.generic import TemplateView
from django.http import JsonResponse

class FailedJobsView(TemplateView):
    """
    View for failed jobs.
    
    This view handles:
    - Failed job listing
    - Error details
    - Retry options
    """
    template_name = 'viewer/failed_jobs.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Failed Jobs'
        return context 