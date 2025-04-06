from django.core.management.base import BaseCommand
from viewer.models import Main, Ingest, Alignment, PostQC
import importlib.util
import sys

class Command(BaseCommand):
    help = 'Test the timestamp rendering methods in the MainTable class'

    def handle(self, *args, **options):
        # Import MainTable directly from the tables.py file
        spec = importlib.util.spec_from_file_location("tables_module", 
                                                     "/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/database_ocs/viewer/tables.py")
        tables_module = importlib.util.module_from_spec(spec)
        sys.modules["tables_module"] = tables_module
        spec.loader.exec_module(tables_module)
        MainTable = tables_module.MainTable
        
        sample = Main.objects.first()
        if not sample:
            self.stdout.write(self.style.ERROR("No samples found in the database"))
            return
            
        self.stdout.write(f"Testing timestamp renders for sample: {sample.fastq_name}")
        
        # Create a new table instance
        table = MainTable([])
        
        # Test Ingest timestamps
        self.stdout.write("\nTESTING INGEST TIMESTAMPS:")
        try:
            ingest = Ingest.objects.get(fastq_name=sample.fastq_name)
            self.stdout.write(f"Raw Ingest start time: {ingest.start_time}")
            self.stdout.write(f"Raw Ingest end time: {ingest.end_time}")
            
            # Test rendering methods
            start_time_render = table.render_ingest_start_time(None, sample)
            end_time_render = table.render_ingest_end_time(None, sample)
            self.stdout.write(f"Rendered Ingest start time: {start_time_render}")
            self.stdout.write(f"Rendered Ingest end time: {end_time_render}")
        except Ingest.DoesNotExist:
            self.stdout.write(self.style.WARNING("No ingest record found"))
        
        # Test Alignment timestamps
        self.stdout.write("\nTESTING ALIGNMENT TIMESTAMPS:")
        try:
            alignment = Alignment.objects.get(fastq_name=sample.fastq_name)
            self.stdout.write(f"Raw Alignment start time: {alignment.start_time}")
            self.stdout.write(f"Raw Alignment end time: {alignment.end_time}")
            
            # Test rendering methods
            start_time_render = table.render_alignment_start_time(None, sample)
            end_time_render = table.render_alignment_end_time(None, sample)
            self.stdout.write(f"Rendered Alignment start time: {start_time_render}")
            self.stdout.write(f"Rendered Alignment end time: {end_time_render}")
        except Alignment.DoesNotExist:
            self.stdout.write(self.style.WARNING("No alignment record found"))
        
        # Test PostQC timestamps
        self.stdout.write("\nTESTING POSTQC TIMESTAMPS:")
        try:
            postqc = PostQC.objects.get(fastq_name=sample.fastq_name)
            self.stdout.write(f"Raw PostQC start time: {postqc.start_time}")
            self.stdout.write(f"Raw PostQC end time: {postqc.end_time}")
            
            # Test rendering methods
            start_time_render = table.render_postqc_start_time(None, sample)
            end_time_render = table.render_postqc_end_time(None, sample)
            self.stdout.write(f"Rendered PostQC start time: {start_time_render}")
            self.stdout.write(f"Rendered PostQC end time: {end_time_render}")
        except PostQC.DoesNotExist:
            self.stdout.write(self.style.WARNING("No postqc record found"))
        
        # Test rendered statuses
        self.stdout.write("\nTESTING STATUS RENDERS:")
        ingest_status = table.render_ingest_status(sample.ingest_status)
        alignment_status = table.render_alignment_status(sample.alignment_status)
        postqc_status = table.render_postqc_status(sample.postqc_status)
        self.stdout.write(f"Ingest status render: {ingest_status}")
        self.stdout.write(f"Alignment status render: {alignment_status}")
        self.stdout.write(f"PostQC status render: {postqc_status}") 