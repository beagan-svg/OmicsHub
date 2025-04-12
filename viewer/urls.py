from django.urls import path
from viewer.views.main import MainListView
from viewer.views.api import metadata_field_view
from viewer.views.pipeline import PipelineDashboardView, PipelineApiView

app_name = 'viewer'

urlpatterns = [
    path('', MainListView.as_view(), name='main_list'),
    path('api/metadata/<str:fastq_name>/<str:field_name>/', metadata_field_view, name='metadata_field'),
    
    # Pipeline URLs
    path('pipeline/', PipelineDashboardView.as_view(), name='pipeline_dashboard'),
    path('api/pipeline/submit-alignment/', PipelineApiView.submit_alignment, name='submit_alignment'),
    path('api/pipeline/check-status/', PipelineApiView.check_alignment_status, name='check_alignment_status'),
] 