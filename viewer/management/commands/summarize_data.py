from django.core.management.base import BaseCommand
from django.db.models import Count
from viewer.models import Metadata, Main, Alignment, PostQC, Ingest

class Command(BaseCommand):
    help = 'Summarize the data in the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed summaries',
        )

    def handle(self, *args, **options):
        detailed = options['detailed']
        
        # Count total records in each table
        self.stdout.write(f'===== DATABASE RECORD COUNTS =====')
        self.stdout.write(f'Metadata records: {Metadata.objects.count()}')
        self.stdout.write(f'Main records: {Main.objects.count()}')
        self.stdout.write(f'Alignment records: {Alignment.objects.count()}')
        self.stdout.write(f'PostQC records: {PostQC.objects.count()}')
        self.stdout.write(f'Ingest records: {Ingest.objects.count()}')
        
        # Count by organism
        self.stdout.write('\n===== RECORDS BY ORGANISM =====')
        organism_counts = Main.objects.values('organism').annotate(count=Count('organism')).order_by('-count')
        for item in organism_counts:
            self.stdout.write(f"{item['organism']}: {item['count']}")
        
        # Count by library prep method
        self.stdout.write('\n===== RECORDS BY LIBRARY PREP METHOD =====')
        library_counts = Main.objects.values('library_prep_method').annotate(count=Count('library_prep_method')).order_by('-count')
        for item in library_counts:
            self.stdout.write(f"{item['library_prep_method']}: {item['count']}")
        
        # Count by study set
        self.stdout.write('\n===== RECORDS BY STUDY SET =====')
        study_counts = Main.objects.values('study_set').annotate(count=Count('study_set')).order_by('-count')
        for item in study_counts[:20]:  # Limit to top 20 to avoid too much output
            self.stdout.write(f"{item['study_set']}: {item['count']}")
        if len(study_counts) > 20:
            self.stdout.write(f"... and {len(study_counts) - 20} more study sets")
        
        # Count by status
        self.stdout.write('\n===== RECORDS BY STATUS =====')
        
        self.stdout.write('Alignment Status:')
        alignment_status_counts = Main.objects.values('alignment_status').annotate(count=Count('alignment_status')).order_by('-count')
        for item in alignment_status_counts:
            self.stdout.write(f"  {item['alignment_status']}: {item['count']}")
        
        self.stdout.write('PostQC Status:')
        postqc_status_counts = Main.objects.values('postqc_status').annotate(count=Count('postqc_status')).order_by('-count')
        for item in postqc_status_counts:
            self.stdout.write(f"  {item['postqc_status']}: {item['count']}")
        
        self.stdout.write('Ingest Status:')
        ingest_status_counts = Main.objects.values('ingest_status').annotate(count=Count('ingest_status')).order_by('-count')
        for item in ingest_status_counts:
            self.stdout.write(f"  {item['ingest_status']}: {item['count']}")
        
        # Detailed information if requested
        if detailed:
            # Check for missing/incomplete records
            self.stdout.write('\n===== MISSING OR INCOMPLETE RECORDS =====')
            
            # Records with missing alignment
            missing_alignment = Main.objects.count() - Alignment.objects.count()
            self.stdout.write(f'Records without alignment: {missing_alignment}')
            
            # Records with missing postQC
            missing_postqc = Main.objects.count() - PostQC.objects.count()
            self.stdout.write(f'Records without postQC: {missing_postqc}')
            
            # Records with missing ingest
            missing_ingest = Main.objects.count() - Ingest.objects.count()
            self.stdout.write(f'Records without ingest: {missing_ingest}')
            
            # Incomplete pipeline (not all COMPLETED)
            incomplete_pipeline = Main.objects.exclude(
                alignment_status='COMPLETED',
                postqc_status='COMPLETED',
                ingest_status='COMPLETED'
            ).count()
            self.stdout.write(f'Records with incomplete pipeline: {incomplete_pipeline}') 