import django_filters
from django.db.models import Q, Count
from django.forms.widgets import CheckboxSelectMultiple
from django.db import connections
from viewer.models import Main, Metadata, LoadAssociation

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
    
    batch_name_from_vendor = django_filters.MultipleChoiceFilter(
        method='filter_batch_name',
        label='Batch Name From Vendor',
        choices=lambda: [(x, x) for x in Metadata.objects.filter(batch_name_from_vendor__isnull=False)
            .exclude(batch_name_from_vendor='').values_list('batch_name_from_vendor', flat=True).distinct()]
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
    
    # Column filters - dynamic filters for any column
    fastq_name_filter = django_filters.CharFilter(method='filter_by_column')
    study_set_filter = django_filters.CharFilter(method='filter_by_column')
    load_name_filter = django_filters.CharFilter(method='filter_by_column')
    batch_name_filter = django_filters.CharFilter(method='filter_by_column')
    batch_name_from_vendor_filter = django_filters.CharFilter(method='filter_by_column')
    cell_capture_filter = django_filters.CharFilter(method='filter_by_column')
    sample_id_filter = django_filters.CharFilter(method='filter_by_column')
    amplification_name_filter = django_filters.CharFilter(method='filter_by_column')
    amplification_id_filter = django_filters.CharFilter(method='filter_by_column')
    cell_prep_type_filter = django_filters.CharFilter(method='filter_by_column')
    sequencing_vendor_filter = django_filters.CharFilter(method='filter_by_column')
    alignment_method_filter = django_filters.CharFilter(method='filter_by_column')
    library_prep_method_filter = django_filters.CharFilter(method='filter_by_column')
    library_prep_method_id_filter = django_filters.CharFilter(method='filter_by_column')
    library_prep_name_filter = django_filters.CharFilter(method='filter_by_column')
    organism_filter = django_filters.CharFilter(method='filter_by_column')
    organism_common_name_filter = django_filters.CharFilter(method='filter_by_column')
    ingest_status_filter = django_filters.CharFilter(method='filter_by_column')
    alignment_status_filter = django_filters.CharFilter(method='filter_by_column')
    postqc_status_filter = django_filters.CharFilter(method='filter_by_column')

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
    
    def filter_by_column(self, queryset, name, value):
        """
        Dynamic column filter method that handles filtering for any column
        based on the field name pattern column_name_filter
        
        Args:
            queryset: The queryset to filter
            name: The filter field name (e.g., 'fastq_name_filter')
            value: Comma-separated string of values to filter by
            
        Returns:
            Filtered queryset
        """
        if not value:
            return queryset
            
        # Extract the actual field name from the filter name
        field_name = name.replace('_filter', '')
        
        # Split the comma-separated values
        values = value.split(',')
        
        # Create a mapping of field names to model fields
        field_mappings = {
            'fastq_name': 'fastq_name__fastq_name',
            'study_set': 'study_set',
            'load_name': 'fastq_name__loadassociation__load_name',
            'batch_name': 'fastq_name__batch_name',
            'batch_name_from_vendor': 'fastq_name__batch_name_from_vendor',
            'cell_capture': 'fastq_name__cell_capture',
            'sample_id': 'fastq_name__fastq_id',
            'amplification_name': 'amplification_name',
            'amplification_id': 'amplification_id',
            'cell_prep_type': 'cell_prep_type',
            'sequencing_vendor': 'sequencing_vendor',
            'alignment_method': 'alignment_method',
            'library_prep_method': 'library_prep_method',
            'library_prep_method_id': 'library_prep_method_id',
            'library_prep_name': 'library_prep_name',
            'organism': 'fastq_name__organism_name',
            'organism_common_name': 'fastq_name__organism_common_name',
            'ingest_status': 'ingest_status',
            'alignment_status': 'alignment_status',
            'postqc_status': 'postqc_status'
        }
        
        # Get the correct field name to filter on
        filter_field = field_mappings.get(field_name, field_name)
        
        # Create Q objects for each value (OR condition)
        q_objects = Q()
        for val in values:
            q_objects |= Q(**{f"{filter_field}__exact": val})
        
        # Apply the filter
        filtered_qs = queryset.filter(q_objects)
        
        return self.apply_distinct(filtered_qs)

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
        
        # Filter by organism_common_name from the related Metadata model
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

    def filter_batch_name(self, queryset, name, values):
        """
        Filter queryset by multiple batch_name_from_vendor values
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
            'batch_name_from_vendor', 
            'load_name', 
            'study_set', 
            'organism',
            'library_prep_method', 
            'alignment_status', 
            'postqc_status', 
            'ingest_status',
            # Column filters
            'fastq_name_filter',
            'study_set_filter',
            'load_name_filter',
            'batch_name_filter',
            'batch_name_from_vendor_filter',
            'cell_capture_filter',
            'sample_id_filter',
            'amplification_name_filter',
            'amplification_id_filter',
            'cell_prep_type_filter',
            'sequencing_vendor_filter',
            'alignment_method_filter',
            'library_prep_method_filter',
            'library_prep_method_id_filter',
            'library_prep_name_filter',
            'organism_filter',
            'organism_common_name_filter',
            'ingest_status_filter',
            'alignment_status_filter',
            'postqc_status_filter'
        ] 