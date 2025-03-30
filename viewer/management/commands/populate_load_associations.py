from django.core.management.base import BaseCommand
from viewer.models import Metadata, LoadAssociation
import json
import os

class Command(BaseCommand):
    help = 'Populates load associations from the JSON file'

    def handle(self, *args, **options):
        # Read JSON file
        json_path = '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
        with open(json_path, 'r') as f:
            json_data = json.load(f)
        
        # Create load associations
        created_count = 0
        error_count = 0
        
        for fastq_name, record in json_data.items():
            try:
                load_name = record.get('Load Name')
                if load_name:
                    metadata = Metadata.objects.get(fastq_name=fastq_name)
                    LoadAssociation.objects.create(
                        fastq_name=metadata,
                        load_name=load_name
                    )
                    created_count += 1
                    if created_count % 100 == 0:
                        self.stdout.write(f"Created {created_count} load associations...")
            except Metadata.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Metadata not found for: {fastq_name}"))
                error_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error creating load association for {fastq_name}: {e}"))
                error_count += 1
        
        self.stdout.write(self.style.SUCCESS(f"Successfully created {created_count} load associations"))
        if error_count > 0:
            self.stdout.write(self.style.WARNING(f"Encountered {error_count} errors")) 