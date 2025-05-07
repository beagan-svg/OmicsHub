import json
from django.utils.safestring import mark_safe
import logging

logger = logging.getLogger(__name__)

def template_utils(request):
    """
    Context processor that provides utility functions to templates.
    Replaces the template filters from viewer_filters.py.
    """
    # Debug logging for request context
    if hasattr(request, 'resolver_match') and request.resolver_match:
        view_name = request.resolver_match.view_name
        logger.debug(f"Context processor called for view: {view_name}")
        
        # Check if we're in a template with pagination
        view_obj = request.resolver_match.func.view_class() if hasattr(request.resolver_match.func, 'view_class') else None
        if view_obj and hasattr(view_obj, 'get_context_data'):
            logger.debug(f"View has get_context_data method")
    
    # Define a debug function to log pagination info
    def debug_pagination_info(page_obj):
        if page_obj:
            logger.debug(f"Page object: {page_obj}")
            logger.debug(f"Page start index: {page_obj.start_index()}")
            logger.debug(f"Page end index: {page_obj.end_index()}")
            if hasattr(page_obj, 'paginator'):
                logger.debug(f"Paginator count: {page_obj.paginator.count}")
            else:
                logger.debug("Page object has no paginator attribute")
        else:
            logger.debug("Page object is None")
        return ""
    
    # Helper function to replace URL parameters
    def param_replace(**kwargs):
        """Replace or add URL parameters."""
        params = request.GET.copy()
        for key, value in kwargs.items():
            params[key] = value
        return params.urlencode()
    
    # Create pagination URL utility for Django templates
    class PaginationUrlHelper:
        def first_page(self):
            """URL for first page"""
            return self._get_url(1)
            
        def prev_page(self, current_page):
            """URL for previous page"""
            try:
                current = int(current_page)
            except (TypeError, ValueError):
                current = 1
            return self._get_url(max(1, current - 1))
            
        def next_page(self, current_page, total_pages):
            """URL for next page"""
            try:
                current = int(current_page)
                total = int(total_pages)
            except (TypeError, ValueError):
                return self._get_url(1)
            return self._get_url(min(total, current + 1))
            
        def last_page(self, total_pages):
            """URL for last page"""
            try:
                total = int(total_pages)
            except (TypeError, ValueError):
                total = 1
            return self._get_url(total)
            
        def _get_url(self, page_number):
            """Internal method to generate URL for the given page number"""
            params = request.GET.copy()
            params['page'] = str(page_number)
            return f"?{params.urlencode()}"
    
    # Create per-page URL utility for Django templates
    class PerPageUrlHelper:
        def get_url(self, per_page):
            """Generate URL for changing rows per page."""
            params = request.GET.copy()
            params['per_page'] = str(per_page)
            params['page'] = '1'  # Reset to first page when changing per_page
            return f"?{params.urlencode()}"
    
    return {
        'utils': {
            # Function to get item from dictionary
            'get_item': lambda dictionary, key: dictionary.get(key, ''),
            
            # Function to split a string
            'split': lambda value, delimiter=',': value.split(delimiter) if value else [],
            
            # Function to check if a value is selected
            'is_selected': lambda value, options_list: 'selected' if value in (options_list or []) else '',
            
            # Function to get pagination info - changed to use string template instead of f-string
            'pagination_info': lambda page_obj: "Results {}-{} of {}".format(
                page_obj.start_index(), page_obj.end_index(), page_obj.paginator.count),
            
            # Function to replace URL parameters
            'param_replace': param_replace,
            
            # Helper classes for pagination URLs that work better with Django templates
            'pagination_url': PaginationUrlHelper(),
            'per_page_url': PerPageUrlHelper(),
            
            # Function to convert a Python object to JSON
            'jsonify': lambda obj: mark_safe(json.dumps(obj)),
            
            # Debug function
            'debug_pagination': debug_pagination_info
        }
    } 