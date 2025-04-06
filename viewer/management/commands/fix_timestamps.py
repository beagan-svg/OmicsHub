from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
import pytz

from viewer.models import Main, Ingest, Alignment, PostQC, Metadata


class Command(BaseCommand):
    help = 'Fix timestamps for test records to match their displayed values'

    def handle(self, *args, **kwargs):
        # Find a test record - use the first one or a specific one
        test_record = Main.objects.first()
        if not test_record:
            self.stdout.write(self.style.ERROR('No Main records found'))
            return
            
        self.stdout.write(f"Fixing timestamps for record: {test_record.fastq_name}")
        
        # Get the current time to use as a base
        now = timezone.now()
        self.stdout.write(f"Current time: {now}")
        
        # Update Ingest timestamps
        try:
            ingest_record = Ingest.objects.get(fastq_name=test_record.fastq_name)
            
            # Set times that make sense (start before end)
            ingest_start = now - timedelta(hours=1)  # 1 hour ago
            ingest_end = now - timedelta(minutes=30)  # 30 minutes ago
            
            ingest_record.start_time = ingest_start
            ingest_record.end_time = ingest_end
            ingest_record.save()
            
            self.stdout.write(self.style.SUCCESS(
                f"Updated Ingest timestamps: \n"
                f"  Start: {ingest_start.strftime('%Y-%m-%d %H:%M:%S %Z')} \n"
                f"  End: {ingest_end.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            ))
        except Ingest.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"No Ingest record found for {test_record.fastq_name}"))
        
        # Update Alignment timestamps
        try:
            alignment_record = Alignment.objects.get(fastq_name=test_record.fastq_name)
            
            # Alignment starts after ingest ends
            alignment_start = now - timedelta(minutes=25)  # 25 minutes ago
            alignment_end = now - timedelta(minutes=15)    # 15 minutes ago
            
            alignment_record.start_time = alignment_start
            alignment_record.end_time = alignment_end
            alignment_record.save()
            
            self.stdout.write(self.style.SUCCESS(
                f"Updated Alignment timestamps: \n"
                f"  Start: {alignment_start.strftime('%Y-%m-%d %H:%M:%S %Z')} \n"
                f"  End: {alignment_end.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            ))
        except Alignment.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"No Alignment record found for {test_record.fastq_name}"))
        
        # Update PostQC timestamps
        try:
            postqc_record = PostQC.objects.get(fastq_name=test_record.fastq_name)
            
            # PostQC starts after alignment ends
            postqc_start = now - timedelta(minutes=10)  # 10 minutes ago
            postqc_end = now - timedelta(minutes=5)     # 5 minutes ago
            
            postqc_record.start_time = postqc_start
            postqc_record.end_time = postqc_end
            postqc_record.save()
            
            self.stdout.write(self.style.SUCCESS(
                f"Updated PostQC timestamps: \n"
                f"  Start: {postqc_start.strftime('%Y-%m-%d %H:%M:%S %Z')} \n"
                f"  End: {postqc_end.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            ))
        except PostQC.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"No PostQC record found for {test_record.fastq_name}"))
            
        # Check all statuses
        try:
            ingest = Ingest.objects.get(fastq_name=test_record.fastq_name)
            self.stdout.write(f"Ingest status: {ingest.status_id}")
            if ingest.status_id != 'COMPLETED':
                ingest.status_id = 'COMPLETED'
                ingest.save()
                self.stdout.write(self.style.SUCCESS("Updated Ingest status to COMPLETED"))
        except Ingest.DoesNotExist:
            pass
            
        try:
            alignment = Alignment.objects.get(fastq_name=test_record.fastq_name)
            self.stdout.write(f"Alignment status: {alignment.status_id}")
            if alignment.status_id != 'COMPLETED':
                alignment.status_id = 'COMPLETED'
                alignment.save()
                self.stdout.write(self.style.SUCCESS("Updated Alignment status to COMPLETED"))
        except Alignment.DoesNotExist:
            pass
            
        try:
            postqc = PostQC.objects.get(fastq_name=test_record.fastq_name)
            self.stdout.write(f"PostQC status: {postqc.status_id}")
            if postqc.status_id != 'COMPLETED':
                postqc.status_id = 'COMPLETED'
                postqc.save()
                self.stdout.write(self.style.SUCCESS("Updated PostQC status to COMPLETED"))
        except PostQC.DoesNotExist:
            pass
            
        self.stdout.write(self.style.SUCCESS(f"All timestamps updated for {test_record.fastq_name}")) 