from django.urls import path

from ocs.views import ProductionMainListView
from ocs.pipeline import (
    pipeline_config,
    PipelineCheckoutView,
    PipelineApiView,
    submit_samples,
    FailedJobsView,
)
from ocs.jobs import JobMonitorView, QueueManagementView
from ocs.queue_views import (
    import_queue,
    get_queue_data,
    remove_queue_item,
    remove_multiple_queue_items,
    clear_queue,
    process_queue,
    move_queue_item,
    queue_control,
)

app_name = 'ocs'

urlpatterns = [
    path('', ProductionMainListView.as_view(), name='ocs-browser'),

    # Pipeline pages
    path('pipeline-checkout/', PipelineCheckoutView.as_view(), name='pipeline_checkout'),
    path('pipeline/jobs/', JobMonitorView.as_view(), name='job_monitor'),
    path('pipeline/queue/', QueueManagementView.as_view(), name='queue_management'),
    path('pipeline/failed/', FailedJobsView.as_view(), name='failed_jobs'),

    # Pipeline API
    path('api/pipeline/config', pipeline_config, name='pipeline_config'),
    path('api/pipeline/check-alignment-status/', PipelineApiView.check_alignment_status, name='check_alignment_status'),
    path('api/pipeline/stop-alignment/', PipelineApiView.stop_alignment, name='stop_alignment'),
    path('api/pipeline/retry-failed-job/', PipelineApiView.retry_failed_job, name='retry_failed_job'),
    path('api/pipeline/cancel-failed-job/', PipelineApiView.cancel_failed_job, name='cancel_failed_job'),
    path('api/pipeline/update_all_jobs/', PipelineApiView.update_all_jobs, name='update_all_jobs'),
    path('api/pipeline/get-job-data/', PipelineApiView.get_job_data, name='get_job_data'),
    path('api/pipeline/submit-samples/', submit_samples, name='submit_samples'),
    path('api/pipeline/check-job-status/<str:demand_id>/', PipelineApiView.check_job_status, name='check_job_status'),
    path('api/pipeline/stop-job/<str:demand_id>/', PipelineApiView.stop_alignment, name='stop_job'),

    # Queue API
    path('api/queue/', get_queue_data, name='get_queue'),
    path('api/queue/import/', import_queue, name='import_queue'),
    path('api/queue/data/', get_queue_data, name='get_queue_data'),
    path('api/queue/remove/', remove_queue_item, name='remove_queue_item'),
    path('api/queue/remove-multiple/', remove_multiple_queue_items, name='remove_multiple_queue_items'),
    path('api/queue/clear/', clear_queue, name='clear_queue'),
    path('api/queue/process/', process_queue, name='process_queue'),
    path('api/queue/move/', move_queue_item, name='move_queue_item'),
    path('api/queue/control/', queue_control, name='queue_control'),
]
