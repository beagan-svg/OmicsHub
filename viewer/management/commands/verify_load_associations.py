import json
import random
from django.core.management.base import BaseCommand
from viewer.models import LoadAssociation, Metadata

class Command(BaseCommand):
    help = 'Verify load associations between study.json and database'

    def add_arguments(self, parser):
        parser.add_argument('--load-name', type=str, help='Specific load name to check')

    def handle(self, *args, **options):
        # Read study.json
        json_path = '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
        with open(json_path, 'r') as f:
            study_data = json.load(f)
        
        # Get database associations
        db_associations = {la.fastq_name.fastq_name: la.load_name for la in LoadAssociation.objects.select_related('fastq_name').all()}
        
        # Create reverse mapping for load names to fastq names
        db_load_to_fastq = {}
        json_load_to_fastq = {}
        
        # Build database mapping
        for fastq_name, load_name in db_associations.items():
            if load_name not in db_load_to_fastq:
                db_load_to_fastq[load_name] = []
            db_load_to_fastq[load_name].append(fastq_name)
        
        # Build study.json mapping
        for fastq_name, record in study_data.items():
            load_name = record.get('Load Name')
            if load_name:
                if load_name not in json_load_to_fastq:
                    json_load_to_fastq[load_name] = []
                json_load_to_fastq[load_name].append(fastq_name)
        
        # Print general results
        self.stdout.write(f"\nTotal entries in study.json with Load Name: {sum(1 for v in study_data.values() if v.get('Load Name'))}")
        self.stdout.write(f"Total entries in database: {len(db_associations)}")
        self.stdout.write(f"Total unique load names: {len(set(db_load_to_fastq.keys()) | set(json_load_to_fastq.keys()))}")
        
        # Check specific load name if provided
        load_name = options.get('load_name')
        if load_name:
            self.stdout.write(f"\nChecking specific Load Name: {load_name}")
            
            db_fastqs = sorted(db_load_to_fastq.get(load_name, []))
            json_fastqs = sorted(json_load_to_fastq.get(load_name, []))
            
            if not db_fastqs and not json_fastqs:
                self.stdout.write("  ⚠ Load name not found in either database or study.json!")
                return
            
            self.stdout.write("  Database fastq names:")
            for fastq in db_fastqs:
                self.stdout.write(f"    - {fastq}")
                # Print additional metadata from study.json
                if fastq in study_data:
                    metadata = study_data[fastq]
                    self.stdout.write(f"      Study Set: {metadata.get('Study Set', 'N/A')}")
                    self.stdout.write(f"      Organism: {metadata.get('Organism', 'N/A')}")
                    self.stdout.write(f"      Library Prep Method: {metadata.get('Library Prep Method', 'N/A')}")
            
            self.stdout.write("\n  Study.json fastq names:")
            for fastq in json_fastqs:
                self.stdout.write(f"    - {fastq}")
                # Print additional metadata from study.json
                if fastq in study_data:
                    metadata = study_data[fastq]
                    self.stdout.write(f"      Study Set: {metadata.get('Study Set', 'N/A')}")
                    self.stdout.write(f"      Organism: {metadata.get('Organism', 'N/A')}")
                    self.stdout.write(f"      Library Prep Method: {metadata.get('Library Prep Method', 'N/A')}")
            
            if set(db_fastqs) == set(json_fastqs):
                self.stdout.write("\n  ✓ Matches perfectly!")
            else:
                self.stdout.write("\n  ✗ Mismatch found!")
                only_in_db = set(db_fastqs) - set(json_fastqs)
                only_in_json = set(json_fastqs) - set(db_fastqs)
                
                if only_in_db:
                    self.stdout.write("    Only in database:")
                    for fastq in sorted(only_in_db):
                        self.stdout.write(f"      - {fastq}")
                
                if only_in_json:
                    self.stdout.write("    Only in study.json:")
                    for fastq in sorted(only_in_json):
                        self.stdout.write(f"      - {fastq}")
        else:
            # Check for overall match
            if not (set(db_load_to_fastq.keys()) ^ set(json_load_to_fastq.keys())):
                all_match = True
                for name in all_load_names:
                    if set(db_load_to_fastq.get(name, [])) != set(json_load_to_fastq.get(name, [])):
                        all_match = False
                        break
                
                if all_match:
                    self.stdout.write("\nAll load associations match perfectly between study.json and database!")
                else:
                    self.stdout.write("\nSome load associations have mismatches in their fastq name mappings.") 