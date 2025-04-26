"""
API endpoints for the viewer application.
"""
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from viewer.core.models import Metadata
from viewer.features.pipeline.pipeline import get_pipeline_config_view
import json
import yaml
import os
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError

@require_http_methods(["GET"])
def metadata_field_view(request, fastq_name, field_name):
    """
    Simple API endpoint to get a specific field from a Metadata record
    """
    metadata = get_object_or_404(Metadata, fastq_name=fastq_name)
    
    # Only allow specific fields to be accessed for security
    allowed_fields = ['batch_name', 'cell_capture']
    
    if field_name not in allowed_fields:
        return JsonResponse({'error': 'Field not allowed'}, status=400)
    
    # Return the field value
    value = getattr(metadata, field_name, None)
    
    return JsonResponse({field_name: value})

@require_http_methods(["GET"])
def pipeline_config(request):
    """
    API endpoint to serve the pipeline configuration from YAML file.
    """
    try:
        print("Loading pipeline configuration...")
        config_path = os.path.join('config', 'pipeline_config.yaml')
        print(f"Config path: {config_path}")
        
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            
        print("Configuration loaded successfully")
        print(f"References: {list(config.get('references', {}).keys())[:3]}")
        print(f"Chemistries: {config.get('chemistries', {})}")
        print(f"Workflows: {list(config.get('workflows', {}).keys())}")
            
        return JsonResponse(config)
    except Exception as e:
        print(f"Error loading pipeline configuration: {str(e)}")
        return JsonResponse({
            'error': str(e),
            'message': 'Failed to load pipeline configuration'
        }, status=500) 