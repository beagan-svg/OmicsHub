from django.urls import path
from viewer.features.data_display.main import MainListView
from viewer.features.api.api import metadata_field_view, pipeline_config
from viewer.features.pipeline.pipeline import (
    PipelineDashboardView, 
    PipelineApiView, 
    submit_samples
)
from viewer.features.job_monitoring.job_monitor import JobMonitorView
from viewer.features.failed_jobs.failed_jobs import FailedJobsView

app_name = 'viewer'

urlpatterns = [
    path('', MainListView.as_view(), name='ocs-browser'),
    path('api/metadata/<str:fastq_name>/<str:field_name>/', metadata_field_view, name='metadata_field'),
    
    # Pipeline URLs
    path('pipeline/', PipelineDashboardView.as_view(), name='pipeline_dashboard'),
    path('pipeline/jobs/', JobMonitorView.as_view(), name='job_monitor'),
    path('pipeline/failed/', FailedJobsView.as_view(), name='failed_jobs'),
    
    # Pipeline API endpoints
    path('api/pipeline/config', pipeline_config, name='pipeline_config'),
    path('api/pipeline/submit-alignment/', PipelineApiView.submit_alignment, name='submit_alignment'),
    path('api/pipeline/check-alignment-status/', PipelineApiView.check_alignment_status, name='check_alignment_status'),
    path('api/pipeline/stop-alignment/', PipelineApiView.stop_alignment, name='stop_alignment'),
    path('api/pipeline/retry-failed-job/', PipelineApiView.retry_failed_job, name='retry_failed_job'),
    path('api/pipeline/update_all_jobs/', PipelineApiView.update_all_jobs, name='update_all_jobs'),
    path('api/pipeline/get-job-data/', PipelineApiView.get_job_data, name='get_job_data'),
    path('api/pipeline/get-queue-data/', PipelineApiView.get_queue_data, name='api_get_queue_data'),
    path('api/pipeline/submit-samples/', submit_samples, name='submit_samples'),
] 