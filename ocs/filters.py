# OCS Browser Sample Filters
# Django filters for filtering and searching sample data in the OCS Browser
# Contains MainFilter class with multi-field search and database optimization

import django_filters
from django.db.models import Q
from django.db import connections
from ocs.models import Main, Metadata, LoadAssociation

# Check if PostgreSQL distinct on is supported
DISTINCT_ON_SUPPORTED = hasattr(django_filters.filterset.FilterSet, 'distinct_fields')

# Check if the database supports DISTINCT ON
def supports_distinct_on():
    """Check if the database supports DISTINCT ON (primarily PostgreSQL)"""
    try:
        # Get the default database connection
        db = connections['default']
        
        # Check database vendor
        return db.vendor == 'postgresql'
    except Exception:
        # Default to False if unable to determine
        return False

# Global flag for distinct on support
DISTINCT_ON_SUPPORTED = supports_distinct_on()

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
    
    batch_rtx = django_filters.MultipleChoiceFilter(
        method='filter_batch_rtx',
        label='RTX Batches',
        choices=lambda: [(x, x) for x in Metadata.objects.filter(batch_name_from_vendor__isnull=False)
            .exclude(batch_name_from_vendor='').filter(batch_name_from_vendor__startswith='RTX')
            .values_list('batch_name_from_vendor', flat=True).distinct()]
    )
    
    batch_mtx = django_filters.MultipleChoiceFilter(
        method='filter_batch_mtx',
        label='MTX Batches',
        choices=lambda: [(x, x) for x in Metadata.objects.filter(batch_name_from_vendor__isnull=False)
            .exclude(batch_name_from_vendor='').filter(batch_name_from_vendor__startswith='MTX')
            .values_list('batch_name_from_vendor', flat=True).distinct()]
    )
    
    batch_atx = django_filters.MultipleChoiceFilter(
        method='filter_batch_atx',
        label='ATX Batches',
        choices=lambda: [(x, x) for x in Metadata.objects.filter(batch_name_from_vendor__isnull=False)
            .exclude(batch_name_from_vendor='').filter(batch_name_from_vendor__startswith='ATX')
            .values_list('batch_name_from_vendor', flat=True).distinct()]
    )
    
    load_name = django_filters.CharFilter(
        method='filter_load_name',
        label='Load Name'
    )
    
    # For all multi-select filters, use method filtering
    study_set = django_filters.MultipleChoiceFilter(
        method='filter_study_set',
        label='Study Set',
        choices=lambda: [(x, x) for x in Main.objects.filter(study_set__isnull=False)
            .exclude(study_set='').values_list('study_set', flat=True).distinct()]
    )
    
    organism = django_filters.MultipleChoiceFilter(
        method='filter_organism',
        label='Organism',
        choices=lambda: [(x, x) for x in Main.objects.filter(organism__isnull=False)
            .exclude(organism='').values_list('organism', flat=True).distinct()]
    )

    # The browser's advanced filter sends "organism_common_name" (the value shown
    # in the UI and used for client-side filtering). Accept it server-side too so
    # the >50k-record fallback filters on the same field.
    organism_common_name = django_filters.MultipleChoiceFilter(
        method='filter_organism_common_name',
        label='Organism Common Name',
        choices=lambda: [(x, x) for x in Metadata.objects.filter(organism_common_name__isnull=False)
            .exclude(organism_common_name='').values_list('organism_common_name', flat=True).distinct()]
    )
    
    library_prep_method = django_filters.MultipleChoiceFilter(
        method='filter_library_prep_method',
        label='Library Prep Method',
        choices=lambda: [(x, x) for x in Main.objects.filter(library_prep_method__isnull=False)
            .exclude(library_prep_method='').values_list('library_prep_method', flat=True).distinct()]
    )
    
    alignment_status = django_filters.MultipleChoiceFilter(
        method='filter_alignment_status',
        label='Alignment Status',
        choices=lambda: [(x, x) for x in Main.objects.filter(alignment_status__isnull=False)
            .exclude(alignment_status='').values_list('alignment_status', flat=True).distinct()]
    )
    
    postqc_status = django_filters.MultipleChoiceFilter(
        method='filter_postqc_status',
        label='PostQC Status',
        choices=lambda: [(x, x) for x in Main.objects.filter(postqc_status__isnull=False)
            .exclude(postqc_status='').values_list('postqc_status', flat=True).distinct()]
    )
    
    ingest_status = django_filters.MultipleChoiceFilter(
        method='filter_ingest_status',
        label='Ingest Status',
        choices=lambda: [(x, x) for x in Main.objects.filter(ingest_status__isnull=False)
            .exclude(ingest_status='').values_list('ingest_status', flat=True).distinct()]
    )

    def apply_distinct(self, queryset):
        """
        Apply distinct on fastq_name__fastq_name if supported,
        otherwise use regular distinct and handle in view
        """
        if DISTINCT_ON_SUPPORTED:
            return queryset.distinct('fastq_name__fastq_name')
        else:
            # For databases that don't support DISTINCT ON, 
            # we'll need to handle the distinct processing at the view level
            return queryset.distinct()

    def filter_search(self, queryset, name, value):
        """
        Filter queryset by searching across multiple fields:
        - fastq_name
        - batch_name_from_vendor
        - load_name
        - organism_common_name
        - library_prep_method
        """
        if not value:
            return queryset
        
        # Get fastq_names that match the load_name search
        matching_load_fastq_names = Metadata.objects.filter(
            loadassociation__load_name__icontains=value
        ).values_list('fastq_name', flat=True)
        
        # Search across multiple fields, avoiding duplicates by using primary key filtering
        filtered_qs = queryset.filter(
            Q(fastq_name__fastq_name__icontains=value) |
            Q(fastq_name__batch_name_from_vendor__icontains=value) |
            Q(fastq_name__fastq_name__in=matching_load_fastq_names) |
            Q(fastq_name__organism_common_name__icontains=value) |
            Q(library_prep_method__icontains=value)
        )
        
        return self.apply_distinct(filtered_qs)
    
    def filter_load_name(self, queryset, name, value):
        """
        Filter queryset by load_name in LoadAssociation model
        """
        if not value:
            return queryset
        
        # Get fastq_names that match the load_name
        matching_fastq_names = Metadata.objects.filter(
            loadassociation__load_name__icontains=value
        ).values_list('fastq_name', flat=True)
        
        # Filter by these fastq_names to avoid duplicates
        filtered_qs = queryset.filter(
            fastq_name__fastq_name__in=matching_fastq_names
        )
        
        return self.apply_distinct(filtered_qs)
    
    def filter_study_set(self, queryset, name, values):
        """
        Filter queryset by multiple study_set values
        """
        if not values:
            return queryset
        
        # Create a Q object for OR conditions
        q_objects = Q()
        for value in values:
            q_objects |= Q(study_set__iexact=value)
        
        # Filter by Q object
        filtered_qs = queryset.filter(q_objects)
        
        return self.apply_distinct(filtered_qs)
    
    def filter_organism(self, queryset, name, values):
        """
        Filter queryset by multiple organism values
        """
        if not values:
            return queryset

        # Filter by organism from the Main table
        filtered_qs = queryset.filter(organism__in=values)
        return self.apply_distinct(filtered_qs)

    def filter_organism_common_name(self, queryset, name, values):
        """
        Filter queryset by multiple organism_common_name values (Metadata field).
        """
        if not values:
            return queryset

        filtered_qs = queryset.filter(fastq_name__organism_common_name__in=values)
        return self.apply_distinct(filtered_qs)
    
    def filter_library_prep_method(self, queryset, name, values):
        """
        Filter queryset by multiple library_prep_method values
        """
        if not values:
            return queryset
        
        filtered_qs = queryset.filter(library_prep_method__in=values)
        return self.apply_distinct(filtered_qs)
    
    def filter_alignment_status(self, queryset, name, values):
        """
        Filter queryset by multiple alignment_status values
        """
        if not values:
            return queryset
        
        filtered_qs = queryset.filter(alignment_status__in=values)
        return self.apply_distinct(filtered_qs)
    
    def filter_postqc_status(self, queryset, name, values):
        """
        Filter queryset by multiple postqc_status values
        """
        if not values:
            return queryset
        
        filtered_qs = queryset.filter(postqc_status__in=values)
        return self.apply_distinct(filtered_qs)
    
    def filter_ingest_status(self, queryset, name, values):
        """
        Filter queryset by multiple ingest_status values
        """
        if not values:
            return queryset
        
        filtered_qs = queryset.filter(ingest_status__in=values)
        return self.apply_distinct(filtered_qs)

    def filter_batch_rtx(self, queryset, name, values):
        """
        Filter queryset by multiple RTX batch values
        """
        if not values:
            return queryset
        
        filtered_qs = queryset.filter(fastq_name__batch_name_from_vendor__in=values)
        return self.apply_distinct(filtered_qs)
    
    def filter_batch_mtx(self, queryset, name, values):
        """
        Filter queryset by multiple MTX batch values
        """
        if not values:
            return queryset
        
        filtered_qs = queryset.filter(fastq_name__batch_name_from_vendor__in=values)
        return self.apply_distinct(filtered_qs)
    
    def filter_batch_atx(self, queryset, name, values):
        """
        Filter queryset by multiple ATX batch values
        """
        if not values:
            return queryset
        
        filtered_qs = queryset.filter(fastq_name__batch_name_from_vendor__in=values)
        return self.apply_distinct(filtered_qs)

    class Meta:
        model = Main
        fields = [
            'search', 
            'fastq_name', 
            'batch_rtx',
            'batch_mtx', 
            'batch_atx',
            'load_name', 
            'study_set',
            'organism',
            'organism_common_name',
            'library_prep_method',
            'alignment_status', 
            'postqc_status', 
            'ingest_status'
        ] 