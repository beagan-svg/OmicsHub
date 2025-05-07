from typing import Dict, Any, List, Optional, Union
from django.shortcuts import render
from django_tables2 import SingleTableView, tables
from django_tables2.export.views import ExportMixin
from django.views.generic import ListView
from django.http import HttpResponse
from django.db.models import Prefetch, Q, QuerySet
import subprocess
from viewer.core.models import Main, Metadata, LoadAssociation, Ingest, Alignment, PostQC
from viewer.features.filters import MainFilter, DISTINCT_ON_SUPPORTED
from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin
from django_tables2.config import RequestConfig
from django.core.paginator import Paginator, Page
from django.utils.safestring import mark_safe

class MainTable(tables.Table):
    fastq_name = tables.Column(verbose_name='Fastq Name', attrs={'th': {'class': 'column-fastq_name'}, 'td': {'class': 'field-fastq_name'}})
    study_set = tables.Column(verbose_name='Study Set', accessor='fastq_name.studies', attrs={'th': {'class': 'column-study_set'}, 'td': {'class': 'field-study_set'}})
    load_name = tables.Column(verbose_name='Load Name', accessor='fastq_name.loadassociation_set.first.load_name', attrs={'th': {'class': 'column-load_name'}, 'td': {'class': 'field-load_name'}})
    library_prep_method = tables.Column(verbose_name='Library Prep Method', accessor='fastq_name.library_prep_method_name', attrs={'th': {'class': 'column-library_prep_method'}, 'td': {'class': 'field-library_prep_method'}})
    organism = tables.Column(verbose_name='Organism', accessor='fastq_name.organism_name', attrs={'th': {'class': 'column-organism'}, 'td': {'class': 'field-organism'}})
    organism_common_name = tables.Column(verbose_name='Organism Common Name', accessor='fastq_name.organism_common_name', attrs={'th': {'class': 'column-organism_common_name'}, 'td': {'class': 'field-organism_common_name'}})
    batch_name = tables.Column(verbose_name='Batch Name', accessor='fastq_name.batch_name', attrs={'th': {'class': 'column-batch_name'}, 'td': {'class': 'field-batch_name'}})
    batch_name_from_vendor = tables.Column(verbose_name='Batch Name From Vendor', accessor='fastq_name.batch_name_from_vendor', attrs={'th': {'class': 'column-batch_name_from_vendor'}, 'td': {'class': 'field-batch_name_from_vendor'}})
    cell_capture = tables.Column(verbose_name='Cell Capture', accessor='fastq_name.cell_capture', attrs={'th': {'class': 'column-cell_capture'}, 'td': {'class': 'field-cell_capture'}})
    sample_id = tables.Column(verbose_name='Sample ID', accessor='fastq_name.sample_id', attrs={'th': {'class': 'column-sample_id'}, 'td': {'class': 'field-sample_id'}})
    amplification_name = tables.Column(verbose_name='Amplification', accessor='fastq_name.amplification_name', attrs={'th': {'class': 'column-amplification_name'}, 'td': {'class': 'field-amplification_name'}})
    amplification_id = tables.Column(verbose_name='Amplification ID', accessor='fastq_name.amplification_id', attrs={'th': {'class': 'column-amplification_id'}, 'td': {'class': 'field-amplification_id'}})
    cell_prep_type = tables.Column(verbose_name='Cell Prep Type', accessor='fastq_name.cell_prep_type', attrs={'th': {'class': 'column-cell_prep_type'}, 'td': {'class': 'field-cell_prep_type'}})
    sequencing_vendor = tables.Column(verbose_name='Sequencing Vendor', accessor='fastq_name.sequencing_vendor', attrs={'th': {'class': 'column-sequencing_vendor'}, 'td': {'class': 'field-sequencing_vendor'}})
    alignment_method = tables.Column(verbose_name='Alignment Method', accessor='fastq_name.alignment_method', attrs={'th': {'class': 'column-alignment_method'}, 'td': {'class': 'field-alignment_method'}})
    library_prep_method_id = tables.Column(verbose_name='Library Prep Method ID', accessor='fastq_name.library_prep_method_id', attrs={'th': {'class': 'column-library_prep_method_id'}, 'td': {'class': 'field-library_prep_method_id'}})
    library_prep_name = tables.Column(verbose_name='Library Prep Name', accessor='fastq_name.library_prep_name', attrs={'th': {'class': 'column-library_prep_name'}, 'td': {'class': 'field-library_prep_name'}})
    ingest_status = tables.Column(
        accessor='ingest_status',
        verbose_name='Ingest Status',
        attrs={
            'td': {'class': 'status-column ingest-status'},
            'th': {'class': 'status-column ingest-status'}
        },
        empty_values=('', None)
    )
    ingest_fid = tables.Column(
        accessor='fastq_name__ingest__fid',
        verbose_name='Ingest FID',
        attrs={
            'td': {'class': 'fid-column ingest-fid'},
            'th': {'class': 'fid-column ingest-fid'}
        },
        empty_values=('', None)
    )
    ingest_start_time = tables.Column(verbose_name='Ingest Start', empty_values=(), attrs={'th': {'class': 'column-ingest_start_time'}, 'td': {'class': 'field-ingest_start_time'}})
    ingest_end_time = tables.Column(verbose_name='Ingest End', empty_values=(), attrs={'th': {'class': 'column-ingest_end_time'}, 'td': {'class': 'field-ingest_end_time'}})
    alignment_status = tables.Column(
        accessor='alignment_status',
        verbose_name='Alignment Status',
        attrs={
            'td': {'class': 'status-column alignment-status'},
            'th': {'class': 'status-column alignment-status'}
        },
        empty_values=('', None)
    )
    alignment_fid = tables.Column(
        accessor='fastq_name__alignment__fid',
        verbose_name='Alignment FID',
        attrs={
            'td': {'class': 'fid-column alignment-fid'},
            'th': {'class': 'fid-column alignment-fid'}
        },
        empty_values=('', None)
    )
    alignment_start_time = tables.Column(verbose_name='Alignment Start', empty_values=(), attrs={'th': {'class': 'column-alignment_start_time'}, 'td': {'class': 'field-alignment_start_time'}})
    alignment_end_time = tables.Column(verbose_name='Alignment End', empty_values=(), attrs={'th': {'class': 'column-alignment_end_time'}, 'td': {'class': 'field-alignment_end_time'}})
    postqc_status = tables.Column(
        accessor='postqc_status',
        verbose_name='PostQC Status',
        attrs={
            'td': {'class': 'status-column postqc-status'},
            'th': {'class': 'status-column postqc-status'}
        },
        empty_values=('', None)
    )
    postqc_fid = tables.Column(
        accessor='fastq_name__postqc__fid',
        verbose_name='PostQC FID',
        attrs={
            'td': {'class': 'fid-column postqc-fid'},
            'th': {'class': 'fid-column postqc-fid'}
        },
        empty_values=('', None)
    )
    postqc_start_time = tables.Column(verbose_name='PostQC Start', empty_values=(), attrs={'th': {'class': 'column-postqc_start_time'}, 'td': {'class': 'field-postqc_start_time'}})
    postqc_end_time = tables.Column(verbose_name='PostQC End', empty_values=(), attrs={'th': {'class': 'column-postqc_end_time'}, 'td': {'class': 'field-postqc_end_time'}})

    def render_study_set(self, value):
        if value:
            return value
        return '—'

    def render_load_name(self, record):
        try:
            load_assoc = record.fastq_name.loadassociation_set.first()
            return load_assoc.load_name if load_assoc else '—'
        except Exception:
            return '—'

    def render_library_prep_method(self, value):
        return value if value and value != 'NA' else '—'

    def render_organism(self, value):
        return value if value and value != 'NA' else '—'

    def render_organism_common_name(self, value):
        return value if value and value != 'NA' else '—'

    def render_batch_name(self, value):
        return value if value and value != 'NA' else '—'

    def render_batch_name_from_vendor(self, value):
        return value if value and value != 'NA' else '—'

    def render_cell_capture(self, value):
        return value if value and value != 'NA' else '—'

    def render_sample_id(self, value):
        return value if value and value != 'NA' else '—'

    def render_amplification_name(self, value):
        return value if value and value != 'NA' else '—'

    def render_amplification_id(self, value):
        return value if value and value != 'NA' else '—'

    def render_cell_prep_type(self, value):
        return value if value and value != 'NA' else '—'

    def render_sequencing_vendor(self, value):
        return value if value and value != 'NA' else '—'

    def render_alignment_method(self, value):
        return value if value and value != 'NA' else '—'

    def render_library_prep_method_id(self, value):
        return value if value and value != 'NA' else '—'

    def render_library_prep_name(self, value):
        return value if value and value != 'NA' else '—'

    def render_ingest_fid(self, value):
        return value if value and value != 'NA' else '—'

    def render_alignment_fid(self, value):
        return value if value and value != 'NA' else '—'

    def render_postqc_fid(self, value):
        return value if value and value != 'NA' else '—'

    def render_ingest_status(self, value):
        if value:
            status = value.lower()
            if status == 'completed' or status == 'complete':
                status_class = 'status-completed'
                label = 'Completed'
            elif status == 'not completed':
                status_class = 'status-not-completed'
                label = 'Not Completed'
            elif 'in progress' in status or status == 'running':
                status_class = 'status-in-progress'
                label = 'In Progress'
            elif 'pending' in status or status == 'submitted' or status == 'queued':
                status_class = 'status-pending'
                label = 'Pending'
            elif 'error' in status or 'fail' in status or 'killed' in status:
                status_class = 'status-error'
                label = value
            else:
                status_class = 'status-not-completed'
                label = value
            return mark_safe(f'<span class="status-badge {status_class}">{label}</span>')
        return mark_safe('<span class="status-badge status-not-completed">Not Started</span>')

    def render_alignment_status(self, value):
        if value:
            status = value.lower()
            if status == 'completed' or status == 'complete':
                status_class = 'status-completed'
                label = 'Completed'
            elif status == 'not completed':
                status_class = 'status-not-completed'
                label = 'Not Completed'
            elif 'in progress' in status or status == 'running':
                status_class = 'status-in-progress'
                label = 'In Progress'
            elif 'pending' in status or status == 'submitted' or status == 'queued':
                status_class = 'status-pending'
                label = 'Pending'
            elif 'error' in status or 'fail' in status or 'killed' in status:
                status_class = 'status-error'
                label = value
            else:
                status_class = 'status-not-completed'
                label = value
            return mark_safe(f'<span class="status-badge {status_class}">{label}</span>')
        return mark_safe('<span class="status-badge status-not-completed">Not Started</span>')

    def render_postqc_status(self, value):
        if value:
            status = value.lower()
            if status == 'completed' or status == 'complete':
                status_class = 'status-completed'
                label = 'Completed'
            elif status == 'not completed':
                status_class = 'status-not-completed'
                label = 'Not Completed'
            elif 'in progress' in status or status == 'running':
                status_class = 'status-in-progress'
                label = 'In Progress'
            elif 'pending' in status or status == 'submitted' or status == 'queued':
                status_class = 'status-pending'
                label = 'Pending'
            elif 'error' in status or 'fail' in status or 'killed' in status:
                status_class = 'status-error'
                label = value
            else:
                status_class = 'status-not-completed'
                label = value
            return mark_safe(f'<span class="status-badge {status_class}">{label}</span>')
        return mark_safe('<span class="status-badge status-not-completed">Not Started</span>')
    
    def render_ingest_start_time(self, value, record):
        """Render Ingest start time"""
        try:
            ingest_record = Ingest.objects.get(fastq_name=record.fastq_name)
            if ingest_record.start_time:
                return ingest_record.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except Ingest.DoesNotExist:
            pass
        return "—"
    
    def render_ingest_end_time(self, value, record):
        """Render Ingest end time"""
        try:
            ingest_record = Ingest.objects.get(fastq_name=record.fastq_name)
            if ingest_record.end_time:
                return ingest_record.end_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except Ingest.DoesNotExist:
            pass
        return "—"
        
    def render_alignment_start_time(self, value, record):
        """Render Alignment start time"""
        try:
            alignment_record = Alignment.objects.get(fastq_name=record.fastq_name)
            if alignment_record.start_time:
                return alignment_record.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except Alignment.DoesNotExist:
            pass
        return "—"
    
    def render_alignment_end_time(self, value, record):
        """Render Alignment end time"""
        try:
            alignment_record = Alignment.objects.get(fastq_name=record.fastq_name)
            if alignment_record.end_time:
                return alignment_record.end_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except Alignment.DoesNotExist:
            pass
        return "—"
    
    def render_postqc_start_time(self, value, record):
        """Render PostQC start time"""
        try:
            postqc_record = PostQC.objects.get(fastq_name=record.fastq_name)
            if postqc_record.start_time:
                return postqc_record.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except PostQC.DoesNotExist:
            pass
        return "—"
    
    def render_postqc_end_time(self, value, record):
        """Render PostQC end time"""
        try:
            postqc_record = PostQC.objects.get(fastq_name=record.fastq_name)
            if postqc_record.end_time:
                return postqc_record.end_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except PostQC.DoesNotExist:
            pass
        return "—"
    
    def order_load_name(self, queryset, is_descending):
        """Custom ordering for load_name column"""
        return queryset.order_by(
            ('-' if is_descending else '') + 'fastq_name__loadassociation__load_name'
        )

    class Meta:
        model = Main
        template_name = "django_tables2/bootstrap5.html"
        fields = ('fastq_name', 'study_set', 'load_name', 'library_prep_method', 
                 'organism', 'organism_common_name', 'batch_name', 'batch_name_from_vendor',
                 'cell_capture', 'sample_id', 'amplification_name', 'amplification_id', 
                 'cell_prep_type', 'sequencing_vendor', 'alignment_method', 
                 'library_prep_method_id', 'library_prep_name', 
                 'ingest_status', 'ingest_fid', 'ingest_start_time', 'ingest_end_time',
                 'alignment_status', 'alignment_fid', 'alignment_start_time', 'alignment_end_time', 
                 'postqc_status', 'postqc_fid', 'postqc_start_time', 'postqc_end_time')
        attrs = {'class': 'table table-striped table-bordered'}

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
    template_name = 'viewer/ocs-browser.html'
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
                
            # Explicitly add pagination data to context
            context['paginator_count'] = page_obj.paginator.count
            context['page_start_index'] = page_obj.start_index()
            context['page_end_index'] = page_obj.end_index()
            context['pagination_info'] = f"Showing {page_obj.start_index()} to {page_obj.end_index()} of {page_obj.paginator.count} samples"
        else:
            context['current_page_count'] = 0
            context['paginator_count'] = 0
            context['page_start_index'] = 0
            context['page_end_index'] = 0
            context['pagination_info'] = "No items to display"

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