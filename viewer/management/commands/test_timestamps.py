from django.core.management.base import BaseCommand
from viewer.models import Main, Ingest, Alignment, PostQC

class Command(BaseCommand):
    help = 'Test timestamp fields in Ingest, Alignment, and PostQC models'

    def handle(self, *args, **options):
        sample = Main.objects.first()
        if not sample:
            self.stdout.write(self.style.ERROR("No samples found in the database"))
            return
            
        self.stdout.write(f"Sample: {sample.fastq_name}")
        
        # Test Ingest timestamps
        self.stdout.write("\nTESTING INGEST TIMESTAMPS:")
        try:
            ingest = Ingest.objects.get(fastq_name=sample.fastq_name)
            self.stdout.write(f"Ingest start time: {ingest.start_time}")
            self.stdout.write(f"Ingest end time: {ingest.end_time}")
        except Ingest.DoesNotExist:
            self.stdout.write(self.style.WARNING("No ingest record found"))
        
        # Test Alignment timestamps
        self.stdout.write("\nTESTING ALIGNMENT TIMESTAMPS:")
        try:
            alignment = Alignment.objects.get(fastq_name=sample.fastq_name)
            self.stdout.write(f"Alignment start time: {alignment.start_time}")
            self.stdout.write(f"Alignment end time: {alignment.end_time}")
        except Alignment.DoesNotExist:
            self.stdout.write(self.style.WARNING("No alignment record found"))
        
        # Test PostQC timestamps
        self.stdout.write("\nTESTING POSTQC TIMESTAMPS:")
        try:
            postqc = PostQC.objects.get(fastq_name=sample.fastq_name)
            self.stdout.write(f"PostQC start time: {postqc.start_time}")
            self.stdout.write(f"PostQC end time: {postqc.end_time}")
        except PostQC.DoesNotExist:
            self.stdout.write(self.style.WARNING("No PostQC record found")) 