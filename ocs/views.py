# OCS Browser Views
# Production-optimized Django views for the OCS Browser with performance improvements
# Contains the main ProductionMainListView and supporting mixins and utilities

import logging
import time
from typing import Dict, Any, List, Optional

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import connection
from django.db.models import Prefetch, QuerySet
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.vary import vary_on_headers

from ocs.models import Main, Metadata, LoadAssociation, Ingest, Alignment, PostQC, UserPreferences
from ocs.columns import DEFAULT_COLUMN_VISIBILITY, effective_column_settings
from .filters import MainFilter, DISTINCT_ON_SUPPORTED
from django_filters.views import FilterView

logger = logging.getLogger(__name__)

# Production Configuration
PRODUCTION_CONFIG = {
    'CACHE_TIMEOUT': 300,  # 5 minutes
    'MAX_PAGE_SIZE': 100,
    'DEFAULT_PAGE_SIZE': 25,
    'ENABLE_QUERY_LOGGING': getattr(settings, 'DEBUG', False),
}

class DatabaseOptimizationMixin:
    """Mixin for database query optimization"""
    
    def get_optimized_queryset(self) -> QuerySet:
        """
        Highly optimized queryset with minimal database hits
        """
        # Use select_related for OneToOne and ForeignKey relationships
        # Use prefetch_related for reverse ForeignKey and ManyToMany relationships
        
        base_queryset = Main.objects.select_related(
            'fastq_name'  # OneToOne relationship to Metadata
        ).prefetch_related(
            # Optimize LoadAssociation prefetch
            Prefetch(
                'fastq_name__loadassociation_set',
                queryset=LoadAssociation.objects.select_related('fastq_name'),
                to_attr='load_associations_cached'
            ),
            # Optimize status table prefetches
            Prefetch(
                'fastq_name__ingest',
                queryset=Ingest.objects.only('fastq_name', 'status_id', 'start_time', 'end_time', 'fid'),
                to_attr='ingest_cached'
            ),
            Prefetch(
                'fastq_name__alignment',
                queryset=Alignment.objects.only('fastq_name', 'status_id', 'start_time', 'end_time', 'fid'),
                to_attr='alignment_cached'
            ),
            Prefetch(
                'fastq_name__postqc',
                queryset=PostQC.objects.only('fastq_name', 'status_id', 'start_time', 'end_time', 'fid'),
                to_attr='postqc_cached'
            )
        ).only(
            # Only fetch required fields to reduce memory usage
            'fastq_name__fastq_name',
            'fastq_name__organism_common_name',
            'fastq_name__batch_name_from_vendor',
            'fastq_name__library_prep_method_name',
            'fastq_name__cell_capture',
            'fastq_name__sample_id',
            'fastq_name__amplification_name',
            'fastq_name__amplification_id',
            'fastq_name__cell_prep_type',
            'fastq_name__sequencing_vendor',
            'fastq_name__alignment_method',
            'fastq_name__library_prep_method_id',
            'fastq_name__library_prep_name',
            'study_set',
            'library_prep_method',
            'organism',
            'alignment_status',
            'postqc_status',
            'ingest_status'
        ).order_by('fastq_name__fastq_name')  # Add explicit ordering to fix UnorderedObjectListWarning
        
        return base_queryset

    def get_cached_filter_options(self) -> Dict[str, List[str]]:
        """
        Get filter options with caching for better performance
        """
        cache_key = 'ocs_browser_filter_options_v2'
        cached_options = cache.get(cache_key)
        
        if cached_options is not None:
            return cached_options
        
        # Use raw SQL for better performance on large datasets
        with connection.cursor() as cursor:
            options = {}
            
            # Get distinct values efficiently
            queries = {
                'study_sets': "SELECT DISTINCT study_set FROM main WHERE study_set IS NOT NULL AND study_set != '' ORDER BY study_set",
                'organism_common_names': "SELECT DISTINCT organism_common_name FROM metadata WHERE organism_common_name IS NOT NULL AND organism_common_name != '' ORDER BY organism_common_name",
                'batch_rtx': "SELECT DISTINCT batch_name_from_vendor FROM metadata WHERE batch_name_from_vendor IS NOT NULL AND batch_name_from_vendor != '' AND batch_name_from_vendor LIKE 'RTX%' ORDER BY batch_name_from_vendor",
                'batch_mtx': "SELECT DISTINCT batch_name_from_vendor FROM metadata WHERE batch_name_from_vendor IS NOT NULL AND batch_name_from_vendor != '' AND batch_name_from_vendor LIKE 'MTX%' ORDER BY batch_name_from_vendor",
                'batch_atx': "SELECT DISTINCT batch_name_from_vendor FROM metadata WHERE batch_name_from_vendor IS NOT NULL AND batch_name_from_vendor != '' AND batch_name_from_vendor LIKE 'ATX%' ORDER BY batch_name_from_vendor",
                'library_prep_methods': "SELECT DISTINCT library_prep_method FROM main WHERE library_prep_method IS NOT NULL AND library_prep_method != '' ORDER BY library_prep_method",
                'alignment_status_options': "SELECT DISTINCT alignment_status FROM main WHERE alignment_status IS NOT NULL AND alignment_status != '' ORDER BY alignment_status",
                'postqc_status_options': "SELECT DISTINCT postqc_status FROM main WHERE postqc_status IS NOT NULL AND postqc_status != '' ORDER BY postqc_status",
                'ingest_status_options': "SELECT DISTINCT ingest_status FROM main WHERE ingest_status IS NOT NULL AND ingest_status != '' ORDER BY ingest_status"
            }
            
            for key, query in queries.items():
                cursor.execute(query)
                options[key] = [row[0] for row in cursor.fetchall()]
        
        # Cache for 5 minutes
        cache.set(cache_key, options, PRODUCTION_CONFIG['CACHE_TIMEOUT'])
        return options

class ResponseOptimizationMixin:
    """Mixin for response optimization"""
    
    def optimize_sample_data(self, sample) -> Dict[str, Any]:
        """
        Optimize sample data serialization for JSON response
        """
        # Use cached relationships to avoid additional queries
        load_name = "—"
        if hasattr(sample.fastq_name, 'load_associations_cached'):
            load_associations = sample.fastq_name.load_associations_cached
            if load_associations:
                load_name = load_associations[0].load_name
        
        # Get status information from cached relationships
        ingest_info = getattr(sample.fastq_name, 'ingest_cached', None)
        alignment_info = getattr(sample.fastq_name, 'alignment_cached', None)
        postqc_info = getattr(sample.fastq_name, 'postqc_cached', None)
        
        return {
            'fastq_name': sample.fastq_name.fastq_name if sample.fastq_name else '',
            'study_set': sample.study_set or '',
            'load_name': load_name,
            'library_prep_method': sample.library_prep_method or '',
            'organism': sample.organism or '',
            'organism_common_name': sample.fastq_name.organism_common_name if sample.fastq_name else '',
            'batch_name_from_vendor': sample.fastq_name.batch_name_from_vendor if sample.fastq_name else '',
            'cell_capture': sample.fastq_name.cell_capture if sample.fastq_name else '',
            'sample_id': sample.fastq_name.sample_id if sample.fastq_name else '',
            'amplification_name': sample.fastq_name.amplification_name if sample.fastq_name else '',
            'amplification_id': sample.fastq_name.amplification_id if sample.fastq_name else '',
            'cell_prep_type': sample.fastq_name.cell_prep_type if sample.fastq_name else '',
            'sequencing_vendor': sample.fastq_name.sequencing_vendor if sample.fastq_name else '',
            'alignment_method': sample.fastq_name.alignment_method if sample.fastq_name else '',
            'library_prep_method_id': sample.fastq_name.library_prep_method_id if sample.fastq_name else '',
            'library_prep_name': sample.fastq_name.library_prep_name if sample.fastq_name else '',
            'ingest_status': sample.ingest_status or 'Not Completed',
            'alignment_status': sample.alignment_status or 'Not Completed',
            'postqc_status': sample.postqc_status or 'Not Completed',
            'ingest_fid': ingest_info.fid if ingest_info else '',
            'alignment_fid': alignment_info.fid if alignment_info else '',
            'postqc_fid': postqc_info.fid if postqc_info else '',
            'ingest_start_time': ingest_info.start_time.isoformat() if ingest_info and ingest_info.start_time else '',
            'ingest_end_time': ingest_info.end_time.isoformat() if ingest_info and ingest_info.end_time else '',
            'alignment_start_time': alignment_info.start_time.isoformat() if alignment_info and alignment_info.start_time else '',
            'alignment_end_time': alignment_info.end_time.isoformat() if alignment_info and alignment_info.end_time else '',
            'postqc_start_time': postqc_info.start_time.isoformat() if postqc_info and postqc_info.start_time else '',
            'postqc_end_time': postqc_info.end_time.isoformat() if postqc_info and postqc_info.end_time else '',
        }

class ProductionMainListView(LoginRequiredMixin, FilterView, DatabaseOptimizationMixin, ResponseOptimizationMixin):
    """
    Production-optimized main view for displaying the sample browser.
    
    Key optimizations:
    - Database query optimization with proper prefetching
    - Response caching for filter options
    - Efficient pagination
    - Compressed JSON responses
    - Query monitoring and logging
    """
    model = Main
    template_name = 'ocs/ocs-browser.html'
    filterset_class = MainFilter
    paginate_by = PRODUCTION_CONFIG['DEFAULT_PAGE_SIZE']
    strict = False

    def get_paginate_by(self, queryset: Optional[QuerySet] = None) -> int:
        """Get pagination size with production limits"""
        per_page = self.request.GET.get('per_page')
        if per_page:
            try:
                per_page = int(per_page)
                # Enforce maximum page size for performance
                return min(per_page, PRODUCTION_CONFIG['MAX_PAGE_SIZE'])
            except (ValueError, TypeError):
                pass
        return self.paginate_by

    def get_queryset(self) -> QuerySet:
        """Get optimized queryset"""
        start_time = time.time()
        
        try:
            queryset = self.get_optimized_queryset()
            
            if PRODUCTION_CONFIG['ENABLE_QUERY_LOGGING']:
                query_time = time.time() - start_time
                logger.info(f"Base queryset generated in {query_time:.3f}s")
                
            return queryset
            
        except Exception as e:
            logger.error(f"Error generating queryset: {str(e)}")
            raise

    def get_filtered_queryset(self) -> QuerySet:
        """Get filtered queryset with optimization"""
        start_time = time.time()
        
        try:
            filtered_qs = self.filterset.qs
            
            if DISTINCT_ON_SUPPORTED:
                filtered_qs = self._handle_postgres_distinct(filtered_qs)
            else:
                filtered_qs = self._handle_standard_distinct(filtered_qs)
            
            if PRODUCTION_CONFIG['ENABLE_QUERY_LOGGING']:
                query_time = time.time() - start_time
                logger.info(f"Filtered queryset generated in {query_time:.3f}s")
                
            return filtered_qs
            
        except Exception as e:
            logger.error(f"Error filtering queryset: {str(e)}")
            raise

    def _handle_postgres_distinct(self, queryset: QuerySet) -> QuerySet:
        """Handle distinct fields for PostgreSQL databases"""
        if hasattr(queryset, 'query') and hasattr(queryset.query, 'distinct_fields') and queryset.query.distinct_fields:
            distinct_fields = queryset.query.distinct_fields
            ordered_fields = list(distinct_fields)
            
            if queryset.query.order_by:
                for field in queryset.query.order_by:
                    if field not in ordered_fields and f"-{field}" not in ordered_fields:
                        ordered_fields.append(field)
            
            return queryset.order_by(*ordered_fields)
        else:
            # Ensure ordering even when no distinct fields - use primary key to maintain consistency
            if not queryset.query.order_by:
                return queryset.order_by('fastq_name__fastq_name')
        return queryset

    def _handle_standard_distinct(self, queryset: QuerySet) -> QuerySet:
        """Handle distinct fields for non-PostgreSQL databases"""
        # Use subquery for better performance on large datasets
        unique_fastq_names = queryset.values_list('fastq_name__fastq_name', flat=True).distinct()
        return queryset.filter(
            fastq_name__fastq_name__in=unique_fastq_names
        ).order_by('fastq_name__fastq_name')

    @method_decorator(vary_on_headers('X-Requested-With', 'Accept'))
    def get(self, request, *args, **kwargs):
        """Handle GET requests with caching optimization"""
        # Check if this is a request for filter options
        if request.GET.get('action') == 'filter-options':
            return self._handle_filter_options_request()
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').startswith('application/json'):
            return self._handle_optimized_ajax_request()
        
        # Normal HTML request with template caching
        return super().get(request, *args, **kwargs)

    def _handle_filter_options_request(self) -> JsonResponse:
        """Handle filter options request"""
        try:
            filter_options = self.get_cached_filter_options()
            return JsonResponse({
                'status': 'success',
                'data': filter_options
            })
        except Exception as e:
            logger.error(f"Error fetching filter options: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Error fetching filter options: {str(e)}'
            }, status=500)

    def _handle_optimized_ajax_request(self) -> JsonResponse:
        """Handle AJAX request with optimizations"""
        start_time = time.time()
        
        try:
            # Check if this is a count-only request
            if self.request.GET.get('count_only'):
                # Get the filtered queryset for counting
                self.filterset = self.get_filterset(self.get_filterset_class())
                filtered_qs = self.get_filtered_queryset()
                
                # Return just the count
                total_count = filtered_qs.count()
                return JsonResponse({
                    'status': 'success',
                    'count': total_count,
                    'total_items': total_count,
                    'pagination': {
                        'total_items': total_count
                    },
                    'query_time': time.time() - start_time
                })
            
            # Check if this is a request for all data (no_pagination)
            if self.request.GET.get('no_pagination'):
                # Get the filtered queryset
                self.filterset = self.get_filterset(self.get_filterset_class())
                filtered_qs = self.get_filtered_queryset()
                
                # Get all samples without pagination
                samples_data = []
                for sample in filtered_qs:
                    sample_data = self.optimize_sample_data(sample)
                    samples_data.append(sample_data)
                
                # Prepare response data
                response_data = {
                    'status': 'success',
                    'samples': samples_data,
                    'pagination': {
                        'current_page': 1,
                        'total_pages': 1,
                        'per_page': len(samples_data),
                        'total_items': len(samples_data),
                        'has_next': False,
                        'has_previous': False,
                    },
                    'query_time': time.time() - start_time
                }
                
                if PRODUCTION_CONFIG['ENABLE_QUERY_LOGGING']:
                    logger.info(f"No-pagination AJAX request completed in {response_data['query_time']:.3f}s, returned {len(samples_data)} samples")
                
                response = JsonResponse(response_data)
                
                # Add caching headers for better performance
                response['Cache-Control'] = 'public, max-age=60'  # Cache for 1 minute
                response['Vary'] = 'Accept, X-Requested-With'
                
                return response
            
            # Regular paginated request
            # Get the filtered queryset
            self.filterset = self.get_filterset(self.get_filterset_class())
            filtered_qs = self.get_filtered_queryset()
            
            # Get pagination info
            paginate_by = self.get_paginate_by(filtered_qs)
            paginator = Paginator(filtered_qs, paginate_by)
            
            page_number = self.request.GET.get('page', 1)
            try:
                page_obj = paginator.page(page_number)
            except (EmptyPage, PageNotAnInteger):
                page_obj = paginator.page(1)
            
            # Optimize sample data serialization
            samples_data = []
            for sample in page_obj.object_list:
                sample_data = self.optimize_sample_data(sample)
                samples_data.append(sample_data)
            
            # Prepare pagination data
            pagination_data = {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'per_page': paginate_by,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
            
            response_data = {
                'status': 'success',
                'samples': samples_data,
                'pagination': pagination_data,
                'query_time': time.time() - start_time
            }
            
            if PRODUCTION_CONFIG['ENABLE_QUERY_LOGGING']:
                logger.info(f"AJAX request completed in {response_data['query_time']:.3f}s")
            
            response = JsonResponse(response_data)
            
            # Add caching headers for better performance
            response['Cache-Control'] = 'public, max-age=60'  # Cache for 1 minute
            response['Vary'] = 'Accept, X-Requested-With'
            
            return response
            
        except Exception as e:
            logger.error(f"Error in AJAX request: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Error loading samples: {str(e)}'
            }, status=500)

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Add optimized context data"""
        start_time = time.time()
        
        context = super().get_context_data(**kwargs)
        
        # Add pagination context
        self._add_pagination_context(context)
        
        # Add cached filter options
        filter_options = self.get_cached_filter_options()
        context.update(filter_options)
        
        # Add request parameters context
        self._add_request_context(context)

        # Column visibility for this user, rendered server-side so the initial
        # paint matches the JS (no flash). Both come from ocs/columns.py.
        prefs = UserPreferences.objects.filter(user=self.request.user).first()
        context['column_settings'] = effective_column_settings(prefs.column_settings if prefs else None)
        context['column_defaults'] = DEFAULT_COLUMN_VISIBILITY

        if PRODUCTION_CONFIG['ENABLE_QUERY_LOGGING']:
            context_time = time.time() - start_time
            logger.info(f"Context data generated in {context_time:.3f}s")
        
        return context



    def _add_pagination_context(self, context: Dict[str, Any]) -> None:
        """Add pagination-related context"""
        # Add pagination constants to context for JavaScript access
        context['pagination_config'] = {
            'PAGE_PARAM': 'page',
            'PER_PAGE_PARAM': 'per_page',
            'DEFAULT_PAGE': 1,
            'DEFAULT_PER_PAGE': PRODUCTION_CONFIG['DEFAULT_PAGE_SIZE'],
            'PER_PAGE_OPTIONS': [10, 25, 50, 100],
            'MAX_PAGE_SIZE': PRODUCTION_CONFIG['MAX_PAGE_SIZE']
        }
        
        # Get current per-page setting
        context['current_per_page'] = self.get_paginate_by(None)
        
        if context.get('page_obj'):
            page_obj = context['page_obj']
            # Store page_obj on the request for the context processor to access
            if hasattr(self, 'request'):
                self.request._current_page_obj = page_obj
                
            context['current_page_count'] = len(page_obj.object_list)
            context['paginator_count'] = page_obj.paginator.count
            context['page_start_index'] = page_obj.start_index()
            context['page_end_index'] = page_obj.end_index()
            
            # Add data-attributes compatible values for JavaScript
            context['pagination_state'] = {
                'current_page': page_obj.number,
                'total_pages': page_obj.paginator.num_pages,
                'per_page': context['current_per_page'],
                'total_items': page_obj.paginator.count,
            }
        else:
            context['current_page_count'] = 0
            context['paginator_count'] = 0
            context['page_start_index'] = 0
            context['page_end_index'] = 0
            
            # Empty pagination state
            context['pagination_state'] = {
                'current_page': 1,
                'total_pages': 1,
                'per_page': context['current_per_page'],
                'total_items': 0,
            }

    def _add_request_context(self, context: Dict[str, Any]) -> None:
        """Add request-related context"""
        context['search_term'] = self.request.GET.get('search', '')
        context['current_filters'] = dict(self.request.GET.items())
        
        if 'per_page' not in context['current_filters'] and context['current_per_page'] != self.paginate_by:
            context['current_filters']['per_page'] = str(context['current_per_page'])
        
        # Add multi-select filter values to context
        multi_select_filters = [
            'study_set', 'organism', 'batch_name_from_vendor', 
            'library_prep_method', 'alignment_status', 
            'postqc_status', 'ingest_status'
        ]
        
        for filter_name in multi_select_filters:
            list_values = self.request.GET.getlist(filter_name)
            context['current_filters'][f"{filter_name}_list"] = list_values if list_values else []

        # Check if any filters are active
        context['has_active_filters'] = any(
            value for key, value in self.request.GET.items()
            if key not in ['page', 'per_page'] and value
        )

 