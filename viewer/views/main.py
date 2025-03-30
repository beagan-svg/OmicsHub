from django.shortcuts import render
from django_tables2 import SingleTableView
from django_tables2.export.views import ExportMixin
from django.views.generic import ListView
from django.http import HttpResponse
from django.db.models import Prefetch, Q
import subprocess
from viewer.models import Main, Metadata, LoadAssociation
from viewer.tables import MainTable
from viewer.filters import MainFilter, DISTINCT_ON_SUPPORTED
from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin
from django_tables2.config import RequestConfig
from django.core.paginator import Paginator

class MainListView(FilterView):
    """
    Main view for displaying the sample browser.
    
    Note: We are inheriting from FilterView directly and manually handling
    the table rendering, rather than using SingleTableMixin which was causing
    pagination issues.
    """
    model = Main
    template_name = 'viewer/main_list.html'
    filterset_class = MainFilter
    paginate_by = 25
    strict = False  # Allow non-model fields to be used in ordering

    def get_queryset(self):
        """
        Optimize the queryset with select_related and prefetch_related
        """
        queryset = Main.objects.select_related(
            'fastq_name'  # This will fetch all metadata fields from the Metadata model
        ).prefetch_related(
            Prefetch(
                'fastq_name__loadassociation_set',
                queryset=LoadAssociation.objects.select_related('fastq_name')
            )
        ).order_by('fastq_name__fastq_name')  # Order by fastq_name for consistent pagination
        
        return queryset

    def get_filtered_queryset(self):
        """
        Get the filtered queryset and ensure proper ordering
        for use with distinct() on fields
        """
        # Get the original filtered queryset
        filtered_qs = self.filterset.qs
        
        # If using PostgreSQL with DISTINCT ON
        if DISTINCT_ON_SUPPORTED:
            # If the queryset uses distinct on fields, we need to make sure the ordering is consistent
            # with the distinct fields to avoid database errors
            if hasattr(filtered_qs, 'query') and hasattr(filtered_qs.query, 'distinct_fields') and filtered_qs.query.distinct_fields:
                # Get the distinct fields
                distinct_fields = filtered_qs.query.distinct_fields
                
                # Add the distinct fields to the ordering to ensure consistency
                if distinct_fields:
                    # Create a new ordered queryset based on the distinct fields, maintaining the original ordering as a secondary sort
                    ordered_fields = list(distinct_fields)
                    if filtered_qs.query.order_by:
                        # Add existing ordering as secondary
                        for field in filtered_qs.query.order_by:
                            if field not in ordered_fields and f"-{field}" not in ordered_fields:
                                ordered_fields.append(field)
                    
                    # Apply the ordering
                    filtered_qs = filtered_qs.order_by(*ordered_fields)
        else:
            # For non-PostgreSQL databases, we need to handle duplicates manually
            # Get the fastq_name values as a set to ensure uniqueness
            unique_fastq_names = set(filtered_qs.values_list('fastq_name__fastq_name', flat=True))
            
            # Filter the original queryset to include only one record per fastq_name
            # This is less efficient but works on all databases
            filtered_qs = filtered_qs.filter(
                fastq_name__fastq_name__in=unique_fastq_names
            ).order_by('fastq_name__fastq_name')
        
        return filtered_qs

    def get_context_data(self, **kwargs):
        """
        Add filter data and table to context.
        
        This is where we handle both filtering and table rendering,
        ensuring pagination works correctly.
        """
        context = super().get_context_data(**kwargs)
        
        # The FilterView already puts the filterset and filtered queryset in the context,
        # along with the paginated page_obj. We need to create a table from the
        # paginated data (object_list).
        
        # Create table from the paginated data
        table = MainTable(data=context['object_list'])
        
        # Configure the table without pagination (the view already handles pagination)
        # We don't pass per_page or enable parameter to avoid errors
        RequestConfig(self.request).configure(table)
        
        context['table'] = table
        
        # Calculate the number of items on the current page
        if context.get('page_obj'):
            page_obj = context['page_obj']
            if page_obj.number == page_obj.paginator.num_pages:
                # Last page - might have fewer items
                context['current_page_count'] = len(page_obj.object_list)
            else:
                # Full page
                context['current_page_count'] = self.paginate_by
        else:
            context['current_page_count'] = 0
        
        # Add batch_name_from_vendor options to context
        context['batch_names_from_vendor'] = sorted(Metadata.objects.filter(
            batch_name_from_vendor__isnull=False
        ).exclude(batch_name_from_vendor='').values_list('batch_name_from_vendor', flat=True).distinct())
        
        # Add filter options to context
        context['study_sets'] = sorted(Main.objects.filter(
            study_set__isnull=False
        ).exclude(study_set='').values_list('study_set', flat=True).distinct())
        
        context['organisms'] = sorted(Main.objects.filter(
            organism__isnull=False
        ).exclude(organism='').values_list('organism', flat=True).distinct())
        
        context['library_prep_methods'] = sorted(Main.objects.filter(
            library_prep_method__isnull=False
        ).exclude(library_prep_method='').values_list('library_prep_method', flat=True).distinct())
        
        # Add alignment, postqc, and ingest status options
        context['alignment_status_options'] = sorted(Main.objects.filter(
            alignment_status__isnull=False
        ).exclude(alignment_status='').values_list('alignment_status', flat=True).distinct())
        
        context['postqc_status_options'] = sorted(Main.objects.filter(
            postqc_status__isnull=False
        ).exclude(postqc_status='').values_list('postqc_status', flat=True).distinct())
        
        context['ingest_status_options'] = sorted(Main.objects.filter(
            ingest_status__isnull=False
        ).exclude(ingest_status='').values_list('ingest_status', flat=True).distinct())
        
        # Add search term to context
        context['search_term'] = self.request.GET.get('search', '')
        
        # Add request parameters to context for form persistence
        context['current_filters'] = dict(self.request.GET.items())
        
        # Handle multiple selection values for the multi-select filters
        multi_select_filters = ['study_set', 'organism', 'library_prep_method', 
                               'alignment_status', 'postqc_status', 'ingest_status', 'batch_name_from_vendor']
        
        has_active_filters = False
        
        for filter_name in multi_select_filters:
            # Use getlist directly which properly handles multiple values
            list_values = self.request.GET.getlist(filter_name)
            
            list_name = f"{filter_name}_list"
            
            # Use list values if present
            if list_values:
                context['current_filters'][list_name] = list_values
                has_active_filters = True
            else:
                context['current_filters'][list_name] = []
        
        # Check other filters to determine if any are active
        for key, value in self.request.GET.items():
            if key not in ['page', 'per_page'] and value and not context.get('has_active_filters', False):
                has_active_filters = True
        
        context['has_active_filters'] = has_active_filters
        
        return context

    def post(self, request, *args, **kwargs):
        if 'submit_batch' in request.POST:
            # Get the filtered queryset
            queryset = self.get_queryset()
            
            # Extract unique values from related Metadata model
            load_names = LoadAssociation.objects.filter(
                fastq_name__in=queryset.values_list('fastq_name', flat=True)
            ).values_list('load_name', flat=True).distinct()
            
            organisms = Metadata.objects.filter(
                fastq_name__in=queryset.values_list('fastq_name', flat=True)
            ).values_list('organism_name', flat=True).distinct()
            
            library_prep_methods = Metadata.objects.filter(
                fastq_name__in=queryset.values_list('fastq_name', flat=True)
            ).values_list('library_prep_method_name', flat=True).distinct()
            
            # Create the command
            cmd = ['./process_batch.sh']
            cmd.extend(load_names)
            cmd.extend(organisms)
            cmd.extend(library_prep_methods)
            
            # Execute the command
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    return HttpResponse("Batch processing started successfully")
                else:
                    return HttpResponse(f"Error: {result.stderr}")
            except Exception as e:
                return HttpResponse(f"Error: {str(e)}")
        
        return super().get(request, *args, **kwargs) 