from django.shortcuts import render
from viewer.models import Metadata

def check_toggles(request):
    """View to debug toggle functionality"""
    metadata_fields = [f.name for f in Metadata._meta.get_fields() 
                     if not f.is_relation and f.name != 'fastq_name']
    
    return render(request, 'viewer/check_toggles.html', {
        'metadata_fields': metadata_fields
    })
