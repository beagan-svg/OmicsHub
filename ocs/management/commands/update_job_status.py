from ocs.pipeline_utils import update_all_running_jobs
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Update status of all running alignment jobs'

    def handle(self, *args, **options):
        self.stdout.write('Updating job statuses...')
        
        results = update_all_running_jobs()
        
        self.stdout.write(self.style.SUCCESS(f'Updated {len(results)} jobs successfully'))
        
        for result in results:
            self.stdout.write(f"FASTQ: {result.get('fastq_name')} - Status: {result.get('new_status')}") 