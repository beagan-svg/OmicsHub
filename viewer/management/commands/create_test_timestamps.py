from django.core.management.base import BaseCommand
from viewer.models import Main, Ingest, Alignment, PostQC, Metadata
from django.utils import timezone
import datetime

class Command(BaseCommand):
    help = 'Create test timestamp records in Ingest, Alignment, and PostQC models'

    def handle(self, *args, **options):
        sample = Main.objects.first()
        if not sample:
            self.stdout.write(self.style.ERROR("No samples found in the database"))
            return
            
        self.stdout.write(f"Using sample: {sample.fastq_name}")
        
        # Create test records with timestamps
        now = timezone.now()
        
        # Ingest record
        ingest, created = Ingest.objects.get_or_create(
            fastq_name=sample.fastq_name,
            defaults={
                'status_id': 'COMPLETED',
                'start_time': now - datetime.timedelta(hours=3),
                'end_time': now - datetime.timedelta(hours=2),
                'fid': 'test-ingest-fid'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS("Created new Ingest record"))
        else:
            ingest.status_id = 'COMPLETED'
            ingest.start_time = now - datetime.timedelta(hours=3)
            ingest.end_time = now - datetime.timedelta(hours=2)
            ingest.save()
            self.stdout.write(self.style.SUCCESS("Updated existing Ingest record"))
        
        # Alignment record
        alignment, created = Alignment.objects.get_or_create(
            fastq_name=sample.fastq_name,
            defaults={
                'status_id': 'COMPLETED',
                'start_time': now - datetime.timedelta(hours=2),
                'end_time': now - datetime.timedelta(hours=1),
                'fid': 'test-alignment-fid'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS("Created new Alignment record"))
        else:
            alignment.status_id = 'COMPLETED'
            alignment.start_time = now - datetime.timedelta(hours=2)
            alignment.end_time = now - datetime.timedelta(hours=1)
            alignment.save()
            self.stdout.write(self.style.SUCCESS("Updated existing Alignment record"))
        
        # PostQC record
        postqc, created = PostQC.objects.get_or_create(
            fastq_name=sample.fastq_name,
            defaults={
                'status_id': 'COMPLETED',
                'start_time': now - datetime.timedelta(hours=1),
                'end_time': now,
                'fid': 'test-postqc-fid'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS("Created new PostQC record"))
        else:
            postqc.status_id = 'COMPLETED'
            postqc.start_time = now - datetime.timedelta(hours=1)
            postqc.end_time = now
            postqc.save()
            self.stdout.write(self.style.SUCCESS("Updated existing PostQC record"))
            
        # Update Main record statuses
        main = sample
        main.alignment_status = 'COMPLETED'
        main.postqc_status = 'COMPLETED'
        main.ingest_status = 'COMPLETED'
        main.save()
        self.stdout.write(self.style.SUCCESS("Updated Main record statuses")) 