from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from viewer.models import Metadata

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