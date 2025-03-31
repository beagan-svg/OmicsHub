from django.urls import path
from viewer.views.main import MainListView
from viewer.views.api import metadata_field_view
from django.views.generic import TemplateView

app_name = 'viewer'

urlpatterns = [
    path('', MainListView.as_view(), name='main_list'),
    path('api/metadata/<str:fastq_name>/<str:field_name>/', metadata_field_view, name='metadata_field'),
    path('test/column-toggle/', TemplateView.as_view(template_name='viewer/column-toggle-test.html'), name='column_toggle_test'),
] 