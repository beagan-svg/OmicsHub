import json
import random
from django.core.management.base import BaseCommand
from viewer.models import Metadata

class Command(BaseCommand):
    help = 'Verify study set associations between study.json and database'

    def handle(self, *args, **options):
        # Read study.json
        json_path = '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
        with open(json_path, 'r') as f:
            study_data = json.load(f)
        
        # Get database study sets
        db_studies = {m.fastq_name: m.studies for m in Metadata.objects.all()}
        
        # Create reverse mapping for study sets to fastq names
        db_study_to_fastq = {}
        json_study_to_fastq = {}
        
        # Build database mapping
        for fastq_name, study_set in db_studies.items():
            if study_set:
                if study_set not in db_study_to_fastq:
                    db_study_to_fastq[study_set] = []
                db_study_to_fastq[study_set].append(fastq_name)
        
        # Build study.json mapping
        for fastq_name, record in study_data.items():
            study_set = record.get('Study Set')
            if study_set:
                if study_set not in json_study_to_fastq:
                    json_study_to_fastq[study_set] = []
                json_study_to_fastq[study_set].append(fastq_name)
        
        # Get some random study sets for detailed checking
        all_study_sets = list(set(db_study_to_fastq.keys()) | set(json_study_to_fastq.keys()))
        sample_size = min(5, len(all_study_sets))
        random_study_sets = random.sample(all_study_sets, sample_size)
        
        # Print general results
        self.stdout.write(f"\nTotal entries in study.json with Study Set: {sum(1 for v in study_data.values() if v.get('Study Set'))}")
        self.stdout.write(f"Total entries in database with Study Set: {sum(1 for v in db_studies.values() if v)}")
        self.stdout.write(f"Total unique study sets: {len(all_study_sets)}")
        
        # Print detailed comparison for random study sets
        self.stdout.write("\nDetailed comparison for random study sets:")
        for study_set in random_study_sets:
            self.stdout.write(f"\nStudy Set: {study_set}")
            
            db_fastqs = sorted(db_study_to_fastq.get(study_set, []))
            json_fastqs = sorted(json_study_to_fastq.get(study_set, []))
            
            self.stdout.write("  Database fastq names:")
            for fastq in db_fastqs:
                self.stdout.write(f"    - {fastq}")
            
            self.stdout.write("  Study.json fastq names:")
            for fastq in json_fastqs:
                self.stdout.write(f"    - {fastq}")
            
            if set(db_fastqs) == set(json_fastqs):
                self.stdout.write("  ✓ Matches perfectly!")
            else:
                self.stdout.write("  ✗ Mismatch found!")
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
        
        # Check for overall match
        if not (set(db_study_to_fastq.keys()) ^ set(json_study_to_fastq.keys())):
            all_match = True
            for study_set in all_study_sets:
                if set(db_study_to_fastq.get(study_set, [])) != set(json_study_to_fastq.get(study_set, [])):
                    all_match = False
                    break
            
            if all_match:
                self.stdout.write("\nAll study set associations match perfectly between study.json and database!")
            else:
                self.stdout.write("\nSome study set associations have mismatches in their fastq name mappings.") 