import django_filters
from django.db.models import Q
from viewer.models import Main, Metadata, LoadAssociation

class MainFilter(django_filters.FilterSet):
    """
    Filter for the Main model, allowing filtering by various fields
    including search across multiple fields.
    """
    search = django_filters.CharFilter(
        method='filter_search',
        label='Search'
    )
    
    fastq_name = django_filters.CharFilter(
        field_name='fastq_name__fastq_name',
        lookup_expr='icontains',
        label='Fastq Name'
    )
    
    load_name = django_filters.CharFilter(
        method='filter_load_name',
        label='Load Name'
    )
    
    study_set = django_filters.CharFilter(
        method='filter_study_set',
        label='Study Set'
    )
    
    organism = django_filters.CharFilter(
        lookup_expr='iexact',
        label='Organism'
    )
    
    library_prep_method = django_filters.CharFilter(
        lookup_expr='iexact',
        label='Library Prep Method'
    )
    
    alignment_status = django_filters.CharFilter(
        lookup_expr='iexact',
        label='Alignment Status'
    )
    
    postqc_status = django_filters.CharFilter(
        lookup_expr='iexact',
        label='PostQC Status'
    )
    
    ingest_status = django_filters.CharFilter(
        lookup_expr='iexact',
        label='Ingest Status'
    )

    def filter_search(self, queryset, name, value):
        """
        Filter queryset by searching across multiple fields:
        - fastq_name
        - load_name
        - organism
        - library_prep_method
        """
        if not value:
            return queryset
        
        # Search across multiple fields
        return queryset.filter(
            Q(fastq_name__fastq_name__icontains=value) |
            Q(fastq_name__loadassociation__load_name__icontains=value) |
            Q(organism__icontains=value) |
            Q(library_prep_method__icontains=value)
        ).distinct()
    
    def filter_load_name(self, queryset, name, value):
        """
        Filter queryset by load_name in LoadAssociation model
        """
        if not value:
            return queryset
        
        # Filter by load_name in LoadAssociation
        return queryset.filter(
            fastq_name__loadassociation__load_name__icontains=value
        ).distinct()
    
    def filter_study_set(self, queryset, name, value):
        """
        Filter queryset by study_set field
        """
        if not value:
            return queryset
        
        # Filter by study_set
        return queryset.filter(
            study_set__iexact=value
        ).distinct()

    class Meta:
        model = Main
        fields = [
            'search', 
            'fastq_name', 
            'load_name', 
            'study_set', 
            'organism',
            'library_prep_method', 
            'alignment_status', 
            'postqc_status', 
            'ingest_status'
        ] 