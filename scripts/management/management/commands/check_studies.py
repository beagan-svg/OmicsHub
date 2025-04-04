from django.core.management.base import BaseCommand
from database_ocs.models import Metadata

class Command(BaseCommand):
    help = 'Check the format of the studies field in Metadata records'

    def handle(self, *args, **options):
        record = Metadata.objects.first()
        self.stdout.write(f"Studies field type: {type(record.studies)}")
        self.stdout.write(f"Studies field value: {record.studies}") 