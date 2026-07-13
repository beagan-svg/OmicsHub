from django.core.management.base import BaseCommand
from django.core.cache import cache
from ocs.jobs import JobMonitorView
from ocs.pipeline import JOB_DATA_CACHE_TIMEOUT, get_cache_key_with_version
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Pre-warm job monitor cache with fresh data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='How often to update cache in seconds (default: 30)',
        )

    def handle(self, *args, **options):
        interval = options['interval']
        
        self.stdout.write(
            self.style.SUCCESS(f'Warming job monitor cache every {interval} seconds...')
        )
        
        try:
            # Create a JobMonitorView instance to access its methods
            view = JobMonitorView()
            
            # Get fresh data
            fresh_data = view._get_fresh_job_data()
            
            # Cache the data with a global key for all users to share
            global_cache_key = get_cache_key_with_version('job_monitor_data_global')
            cache.set(global_cache_key, fresh_data, timeout=JOB_DATA_CACHE_TIMEOUT)
            
            # Also update job counts cache
            counts_cache_key = get_cache_key_with_version('job_counts_global')
            cache.set(counts_cache_key, fresh_data.get('job_counts', {}), timeout=JOB_DATA_CACHE_TIMEOUT)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully warmed cache with {len(fresh_data.get("running_jobs", []))} running jobs '
                    f'and {len(fresh_data.get("completed_jobs", []))} completed jobs'
                )
            )
            
            logger.info("Job monitor cache warmed successfully")
            
        except Exception as e:
            error_msg = f"Error warming job monitor cache: {str(e)}"
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg) 