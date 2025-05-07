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
    
    # Helper function to create pagination URLs
    def pagination_url(page=1, exclude_keys=None):
        """
        Generate URL for pagination with current GET parameters.
        
        Args:
            page: The page number to set in the URL
            exclude_keys: List of keys to exclude from URL parameters
            
        Returns:
            String: URL with query parameters
        """
        if exclude_keys is None:
            exclude_keys = ['page', 'csrfmiddlewaretoken']
        elif isinstance(exclude_keys, str):
            exclude_keys = [exclude_keys, 'csrfmiddlewaretoken']
            
        params = []
        
        # Add regular GET parameters
        for key, value in request.GET.items():
            if key not in exclude_keys and value:
                params.append(f"{key}={value}")
                
        # Add page parameter
        params.append(f"page={page}")
        
        return "?" + "&".join(params)
    
    # Helper function for per page URLs
    def per_page_url(per_page, page=1):
        """
        Generate URL for changing rows per page.
        
        Args:
            per_page: Number of rows per page
            page: Page number to navigate to (default 1)
            
        Returns:
            String: URL with query parameters
        """
        params = []
        
        # Add all GET parameters except page and per_page
        for key, value in request.GET.items():
            if key not in ['page', 'per_page', 'csrfmiddlewaretoken'] and value:
                params.append(f"{key}={value}")
        
        # Add per_page and page parameters
        params.append(f"per_page={per_page}")
        params.append(f"page={page}")
        
        return "?" + "&".join(params)
    
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
            
            # Function to generate pagination URLs
            'pagination_url': pagination_url,
            
            # Function to generate per page URLs
            'per_page_url': per_page_url,
            
            # Function to convert a Python object to JSON
            'jsonify': lambda obj: mark_safe(json.dumps(obj)),
            
            # Debug function
            'debug_pagination': debug_pagination_info
        }
    } 