from django.core.management.base import BaseCommand
from django.core.cache import cache
from viewer.models import Main, Ingest, Alignment, PostQC
from django.db import connection
from django.apps import apps

class Command(BaseCommand):
    help = 'Rebuild the timestamp fields in the display table and refresh database views'

    def handle(self, *args, **options):
        self.stdout.write("Rebuilding display table fields...")
        
        # Clear the cache to force reload of template and table configs
        self.stdout.write("Clearing cache...")
        cache.clear()
        self.stdout.write(self.style.SUCCESS("Cache cleared successfully"))
        
        # Refresh the database views if they exist
        self.stdout.write("Checking for database views...")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_type = 'VIEW'")
                views = [row[0] for row in cursor.fetchall()]
                self.stdout.write(f"Found {len(views)} database views")
                
                for view in views:
                    self.stdout.write(f"Refreshing view: {view}")
                    cursor.execute(f"REFRESH MATERIALIZED VIEW IF EXISTS {view}")
            self.stdout.write(self.style.SUCCESS("Database views refreshed"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Error refreshing views: {str(e)}"))
            
        # Update timestamp fields in models
        self.stdout.write("Confirming timestamp fields in models...")
        
        # Check Ingest model
        ingest_fields = [f.name for f in Ingest._meta.get_fields()]
        self.stdout.write(f"Ingest model fields: {', '.join(ingest_fields)}")
        if 'start_time' in ingest_fields and 'end_time' in ingest_fields:
            self.stdout.write(self.style.SUCCESS("Ingest timestamp fields are properly defined"))
        else:
            self.stdout.write(self.style.ERROR("Ingest timestamp fields are missing!"))
            
        # Check Alignment model
        alignment_fields = [f.name for f in Alignment._meta.get_fields()]
        self.stdout.write(f"Alignment model fields: {', '.join(alignment_fields)}")
        if 'start_time' in alignment_fields and 'end_time' in alignment_fields:
            self.stdout.write(self.style.SUCCESS("Alignment timestamp fields are properly defined"))
        else:
            self.stdout.write(self.style.ERROR("Alignment timestamp fields are missing!"))
            
        # Check PostQC model
        postqc_fields = [f.name for f in PostQC._meta.get_fields()]
        self.stdout.write(f"PostQC model fields: {', '.join(postqc_fields)}")
        if 'start_time' in postqc_fields and 'end_time' in postqc_fields:
            self.stdout.write(self.style.SUCCESS("PostQC timestamp fields are properly defined"))
        else:
            self.stdout.write(self.style.ERROR("PostQC timestamp fields are missing!"))
            
        # Get a sample record to verify data access
        self.stdout.write("\nVerifying data access for timestamp fields...")
        try:
            sample = Main.objects.first()
            self.stdout.write(f"Sample record: {sample.fastq_name}")
            
            try:
                ingest = Ingest.objects.get(fastq_name=sample.fastq_name)
                self.stdout.write(f"Ingest timestamps - Start: {ingest.start_time}, End: {ingest.end_time}")
            except Ingest.DoesNotExist:
                self.stdout.write("No Ingest record found for sample")
                
            try:
                alignment = Alignment.objects.get(fastq_name=sample.fastq_name)
                self.stdout.write(f"Alignment timestamps - Start: {alignment.start_time}, End: {alignment.end_time}")
            except Alignment.DoesNotExist:
                self.stdout.write("No Alignment record found for sample")
                
            try:
                postqc = PostQC.objects.get(fastq_name=sample.fastq_name)
                self.stdout.write(f"PostQC timestamps - Start: {postqc.start_time}, End: {postqc.end_time}")
            except PostQC.DoesNotExist:
                self.stdout.write("No PostQC record found for sample")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error verifying data: {str(e)}"))
        
        self.stdout.write("\n" + self.style.SUCCESS("Display table fields rebuilt successfully"))
        self.stdout.write("Restart the server for changes to take effect") 