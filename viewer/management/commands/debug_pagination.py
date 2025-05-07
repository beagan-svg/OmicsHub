import logging
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
from viewer.models import Main

class Command(BaseCommand):
    help = 'Debug pagination objects in Django'

    def handle(self, *args, **options):
        # Set up logging
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger('pagination_debug')
        
        # Get a queryset to paginate
        queryset = Main.objects.all()
        logger.info(f"Total count in queryset: {queryset.count()}")
        
        # Create a paginator
        paginator = Paginator(queryset, 10)
        logger.info(f"Paginator object: {paginator}")
        logger.info(f"Paginator count: {paginator.count}")
        logger.info(f"Paginator num_pages: {paginator.num_pages}")
        
        # Get a page
        page = paginator.get_page(1)
        logger.info(f"Page object: {page}")
        logger.info(f"Page has_next: {page.has_next()}")
        logger.info(f"Page has_previous: {page.has_previous()}")
        logger.info(f"Page number: {page.number}")
        
        # Test accessing attributes directly vs through methods
        try:
            logger.info(f"Page start_index: {page.start_index}")
            logger.info(f"Page end_index: {page.end_index}")
        except Exception as e:
            logger.error(f"Error accessing attributes directly: {e}")
        
        try:
            logger.info(f"Page start_index(): {page.start_index()}")
            logger.info(f"Page end_index(): {page.end_index()}")
        except Exception as e:
            logger.error(f"Error calling methods: {e}")
        
        # Test accessing paginator through page
        try:
            logger.info(f"Page paginator: {page.paginator}")
            logger.info(f"Page paginator count: {page.paginator.count}")
        except Exception as e:
            logger.error(f"Error accessing paginator through page: {e}")
        
        # Test a custom pagination_info function like in the context processor
        try:
            pagination_info = f"Results {page.start_index()}-{page.end_index()} of {page.paginator.count}"
            logger.info(f"Custom pagination_info: {pagination_info}")
        except Exception as e:
            logger.error(f"Error in custom pagination_info: {e}")
            
        # Test with format
        try:
            pagination_info = "Results {}-{} of {}".format(
                page.start_index(), page.end_index(), page.paginator.count)
            logger.info(f"Custom pagination_info with format: {pagination_info}")
        except Exception as e:
            logger.error(f"Error in custom pagination_info with format: {e}") 