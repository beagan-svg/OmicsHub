import json
from django.utils.safestring import mark_safe
import logging

logger = logging.getLogger(__name__)

def template_utils(request):
    """
    Context processor that provides utility functions to templates.
    """
    # Debug logging for request context
    if hasattr(request, 'resolver_match') and request.resolver_match:
        view_name = request.resolver_match.view_name
        logger.debug(f"Context processor called for view: {view_name}")
        
        # Check if we're in a template with pagination
        view_obj = request.resolver_match.func.view_class() if hasattr(request.resolver_match.func, 'view_class') else None
        if view_obj and hasattr(view_obj, 'get_context_data'):
            logger.debug(f"View has get_context_data method")
    
    # Helper function to replace URL parameters
    def param_replace(**kwargs):
        """Replace or add URL parameters."""
        params = request.GET.copy()
        for key, value in kwargs.items():
            params[key] = value
        return params.urlencode()
    
    # Utility for creating pagination URLs
    def create_page_url(page_number):
        """Create a URL for the given page number, preserving other query parameters."""
        params = request.GET.copy()
        params['page'] = str(page_number)
        return f"?{params.urlencode()}"
        
    # Default pagination URLs for common actions
    # These don't take parameters to ensure they work in Django templates
    def first_page_url():
        """URL for the first page."""
        return create_page_url(1)
        
    def previous_page_url():
        """URL for the previous page based on the current request."""
        current_page = int(request.GET.get('page', '1'))
        return create_page_url(max(1, current_page - 1))
        
    def next_page_url():
        """URL for the next page based on the current request."""
        current_page = int(request.GET.get('page', '1'))
        # This doesn't have max page information - best effort
        return create_page_url(current_page + 1)
        
    def last_page_url():
        """
        URL for the last page based on available context information.
        
        Retrieves the total page count from the request's _current_page_obj
        if available.
        """
        # Try to get the page count from the stored page object on the request
        if hasattr(request, '_current_page_obj'):
            page_obj = request._current_page_obj
            if hasattr(page_obj, 'paginator') and hasattr(page_obj.paginator, 'num_pages'):
                return create_page_url(page_obj.paginator.num_pages)
                
        # Default to page 1 if we can't determine the last page
        return create_page_url(1)
    
    # Utility for per-page changes that works without parameters
    def per_page_url_10():
        """URL for 10 rows per page."""
        return _create_per_page_url(10)
        
    def per_page_url_25():
        """URL for 25 rows per page."""
        return _create_per_page_url(25)
        
    def per_page_url_50():
        """URL for 50 rows per page."""
        return _create_per_page_url(50)
        
    def per_page_url_100():
        """URL for 100 rows per page."""
        return _create_per_page_url(100)
    
    def _create_per_page_url(per_page):
        """Create a URL for changing rows per page."""
        params = request.GET.copy()
        params['per_page'] = str(per_page)
        params['page'] = '1'  # Reset to first page
        return f"?{params.urlencode()}"
    
    # Function to get pagination info for the current page
    def pagination_info():
        """Get pagination info string for the current page."""
        # Try to get page_obj from the request context
        if hasattr(request, '_current_page_obj'):
            page_obj = request._current_page_obj
            return f"Showing {page_obj.start_index()} to {page_obj.end_index()} of {page_obj.paginator.count} samples"
        return "No items to display"
    
    return {
        'utils': {
            # Function to get item from dictionary
            'get_item': lambda dictionary, key: dictionary.get(key, ''),
            
            # Function to split a string
            'split': lambda value, delimiter=',': value.split(delimiter) if value else [],
            
            # Function to check if a value is selected
            'is_selected': lambda value, options_list: 'selected' if value in (options_list or []) else '',
            
            # Function to get pagination info - no parameters needed
            'pagination_info': pagination_info,
            
            # Function to replace URL parameters
            'param_replace': param_replace,
            
            # Pagination URL helpers that work in Django templates
            'first_page_url': first_page_url,
            'previous_page_url': previous_page_url,
            'next_page_url': next_page_url,
            'last_page_url': last_page_url,
            
            # Per-page URL helpers
            'per_page_url_10': per_page_url_10,
            'per_page_url_25': per_page_url_25,
            'per_page_url_50': per_page_url_50,
            'per_page_url_100': per_page_url_100
        }
    } 