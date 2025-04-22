from typing import Dict, Any, List, Optional, Union
from django.shortcuts import render
from django_tables2 import SingleTableView
from django_tables2.export.views import ExportMixin
from django.views.generic import ListView
from django.http import HttpResponse
from django.db.models import Prefetch, Q, QuerySet
import subprocess
from viewer.models import Main, Metadata, LoadAssociation
from viewer.tables import MainTable
from viewer.filters import MainFilter, DISTINCT_ON_SUPPORTED
from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin
from django_tables2.config import RequestConfig
from django.core.paginator import Paginator, Page

class MainListView(FilterView):
    """
    Main view for displaying the sample browser.
    
    This view handles:
    - Sample filtering and pagination
    - Table rendering and export
    - Batch processing submission
    - User preferences management
    
    Note: We are inheriting from FilterView directly and manually handling
    the table rendering, rather than using SingleTableMixin which was causing
    pagination issues.
    """
    model = Main
    template_name = 'viewer/main_list.html'
    filterset_class = MainFilter
    paginate_by = 25
    strict = False  # Allow non-model fields to be used in ordering

    def get_paginate_by(self, queryset: Optional[QuerySet] = None) -> int:
        """
        Get the number of items to paginate by, or the default.
        
        Args:
            queryset: Optional queryset (not used in this implementation)
            
        Returns:
            int: Number of items per page
        """
        per_page = self.request.GET.get('per_page')
        if per_page in ['10', '25', '50', '100']:
            return int(per_page)
        return self.paginate_by

    def get_queryset(self) -> QuerySet:
        """
        Optimize the queryset with select_related and prefetch_related.
        
        Returns:
            QuerySet: Optimized queryset with related data
        """
        return Main.objects.select_related(
            'fastq_name'
        ).prefetch_related(
            Prefetch(
                'fastq_name__loadassociation_set',
                queryset=LoadAssociation.objects.select_related('fastq_name')
            ),
            Prefetch(
                'fastq_name__alignment',
                to_attr='alignment_info'
            ),
            Prefetch(
                'fastq_name__postqc',
                to_attr='postqc_info'
            ),
            Prefetch(
                'fastq_name__ingest',
                to_attr='ingest_info'
            )
        ).order_by('fastq_name__fastq_name')

    def get_filtered_queryset(self) -> QuerySet:
        """
        Get the filtered queryset and ensure proper ordering for use with distinct().
        
        Returns:
            QuerySet: Filtered and properly ordered queryset
        """
        filtered_qs = self.filterset.qs
        
        if DISTINCT_ON_SUPPORTED:
            return self._handle_postgres_distinct(filtered_qs)
        return self._handle_standard_distinct(filtered_qs)

    def _handle_postgres_distinct(self, queryset: QuerySet) -> QuerySet:
        """
        Handle distinct fields for PostgreSQL databases.
        
        Args:
            queryset: Original filtered queryset
            
        Returns:
            QuerySet: Ordered queryset with distinct fields
        """
        if hasattr(queryset, 'query') and hasattr(queryset.query, 'distinct_fields') and queryset.query.distinct_fields:
            distinct_fields = queryset.query.distinct_fields
            ordered_fields = list(distinct_fields)
            
            if queryset.query.order_by:
                for field in queryset.query.order_by:
                    if field not in ordered_fields and f"-{field}" not in ordered_fields:
                        ordered_fields.append(field)
            
            return queryset.order_by(*ordered_fields)
        return queryset

    def _handle_standard_distinct(self, queryset: QuerySet) -> QuerySet:
        """
        Handle distinct fields for non-PostgreSQL databases.
        
        Args:
            queryset: Original filtered queryset
            
        Returns:
            QuerySet: Filtered queryset with unique fastq_names
        """
        unique_fastq_names = set(queryset.values_list('fastq_name__fastq_name', flat=True))
        return queryset.filter(
            fastq_name__fastq_name__in=unique_fastq_names
        ).order_by('fastq_name__fastq_name')

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """
        Add filter data and table to context.
        
        Returns:
            Dict[str, Any]: Context dictionary with all necessary data
        """
        context = super().get_context_data(**kwargs)
        
        # Add pagination context
        self._add_pagination_context(context)
        
        # Add table context
        self._add_table_context(context)
        
        # Add filter options context
        self._add_filter_options_context(context)
        
        # Add request parameters context
        self._add_request_context(context)
        
        return context

    def _add_pagination_context(self, context: Dict[str, Any]) -> None:
        """Add pagination-related context."""
        context['current_per_page'] = self.get_paginate_by(None)
        
        if context.get('page_obj'):
            page_obj = context['page_obj']
            if page_obj.number == page_obj.paginator.num_pages:
                context['current_page_count'] = len(page_obj.object_list)
            else:
                context['current_page_count'] = self.paginate_by
        else:
            context['current_page_count'] = 0

    def _add_table_context(self, context: Dict[str, Any]) -> None:
        """Add table-related context."""
        table = MainTable(data=context['object_list'])
        RequestConfig(self.request).configure(table)
        context['table'] = table

    def _add_filter_options_context(self, context: Dict[str, Any]) -> None:
        """Add filter options to context."""
        context.update({
            'study_sets': self._get_distinct_values(Main, 'study_set'),
            'organisms': self._get_distinct_values(Metadata, 'organism_common_name'),
            'batch_names_from_vendor': self._get_distinct_values(Metadata, 'batch_name_from_vendor'),
            'library_prep_methods': self._get_distinct_values(Main, 'library_prep_method'),
            'alignment_status_options': self._get_distinct_values(Main, 'alignment_status'),
            'postqc_status_options': self._get_distinct_values(Main, 'postqc_status'),
            'ingest_status_options': self._get_distinct_values(Main, 'ingest_status')
        })

    def _get_distinct_values(self, model: Any, field: str) -> List[str]:
        """Get distinct values for a field from a model."""
        return sorted(model.objects.filter(
            **{f"{field}__isnull": False}
        ).exclude(**{field: ''}).values_list(field, flat=True).distinct())

    def _add_request_context(self, context: Dict[str, Any]) -> None:
        """Add request-related context."""
        context['search_term'] = self.request.GET.get('search', '')
        context['current_filters'] = dict(self.request.GET.items())
        
        if 'per_page' not in context['current_filters'] and context['current_per_page'] != self.paginate_by:
            context['current_filters']['per_page'] = str(context['current_per_page'])
        
        self._add_multi_select_filters(context)
        self._add_column_filters(context)
        context['has_active_filters'] = self._check_active_filters(context)

    def _add_multi_select_filters(self, context: Dict[str, Any]) -> None:
        """Add multi-select filter values to context."""
        multi_select_filters = [
            'study_set', 'organism', 'batch_name_from_vendor', 
            'library_prep_method', 'alignment_status', 
            'postqc_status', 'ingest_status'
        ]
        
        for filter_name in multi_select_filters:
            list_values = self.request.GET.getlist(filter_name)
            context['current_filters'][f"{filter_name}_list"] = list_values if list_values else []

    def _add_column_filters(self, context: Dict[str, Any]) -> None:
        """Add column filter values to context."""
        # Collect all column filter parameters
        column_filters = {}
        for key, value in self.request.GET.items():
            if key.endswith('_filter') and value:
                base_key = key.replace('_filter', '')
                column_filters[base_key] = value.split(',')
                
        context['column_filters'] = column_filters

    def _check_active_filters(self, context: Dict[str, Any]) -> bool:
        """Check if any filters are active."""
        for key, value in self.request.GET.items():
            if key not in ['page', 'per_page'] and value:
                return True
        return False

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Handle POST requests for batch processing.
        
        Args:
            request: HTTP request object
            
        Returns:
            HttpResponse: Response with processing status
        """
        if 'submit_batch' in request.POST:
            return self._handle_batch_submission()
        return super().get(request, *args, **kwargs)

    def _handle_batch_submission(self) -> HttpResponse:
        """Handle batch processing submission."""
        queryset = self.get_queryset()
        
        load_names = LoadAssociation.objects.filter(
            fastq_name__in=queryset.values_list('fastq_name', flat=True)
        ).values_list('load_name', flat=True).distinct()
        
        organisms = Metadata.objects.filter(
            fastq_name__in=queryset.values_list('fastq_name', flat=True)
        ).values_list('organism_name', flat=True).distinct()
        
        library_prep_methods = Metadata.objects.filter(
            fastq_name__in=queryset.values_list('fastq_name', flat=True)
        ).values_list('library_prep_method_name', flat=True).distinct()
        
        cmd = ['./process_batch.sh']
        cmd.extend(load_names)
        cmd.extend(organisms)
        cmd.extend(library_prep_methods)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return HttpResponse("Batch processing started successfully")
            return HttpResponse(f"Error: {result.stderr}")
        except Exception as e:
            return HttpResponse(f"Error: {str(e)}") 