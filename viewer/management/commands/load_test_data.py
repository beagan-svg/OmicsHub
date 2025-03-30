import json
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import datetime
from viewer.models import Metadata, Main, LoadAssociation, Alignment, Ingest, PostQC

def parse_datetime(dt_str):
    """Parse datetime string, return None for NA values"""
    if dt_str == "NA":
        return None
    try:
        return datetime.fromisoformat(dt_str.replace('+00:00', ''))
    except (ValueError, TypeError):
        return None

def clean_study_set(study_set):
    """Ensure the study set is a clean string without JSON formatting"""
    if isinstance(study_set, list):
        # If it's a list, join the elements with '+' (common separator for multiple studies)
        return '+'.join(filter(None, study_set))
    elif isinstance(study_set, str):
        # If it's a string but looks like JSON, clean it
        if study_set.startswith('[') and study_set.endswith(']'):
            try:
                # Try to parse as JSON
                parsed = json.loads(study_set)
                if isinstance(parsed, list):
                    return '+'.join(filter(None, parsed))
            except json.JSONDecodeError:
                # If parsing fails, remove brackets manually
                study_set = study_set.strip('[]').strip()
                # Remove quotes if present
                if (study_set.startswith('"') and study_set.endswith('"')) or (study_set.startswith("'") and study_set.endswith("'")):
                    study_set = study_set[1:-1]
        return study_set
    elif study_set is None:
        return ""
    else:
        return str(study_set)

class Command(BaseCommand):
    help = 'Load test data from study.json'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of records to load (default: all records)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before loading',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        clear = options['clear']
        
        # Clear existing data if requested
        if clear:
            self.stdout.write('Clearing existing data...')
            Metadata.objects.all().delete()
        
        # Path to the JSON file
        json_path = '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
        
        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f'File not found: {json_path}'))
            return
        
        # Load the JSON data
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        limit_str = f'up to {limit}' if limit else 'all'
        self.stdout.write(f'Loading {limit_str} records from study.json...')
        
        # Process records
        records_processed = 0
        metadata_count = 0
        main_count = 0
        load_association_count = 0
        alignment_count = 0
        postqc_count = 0
        ingest_count = 0
        
        # Limit the number of records if specified
        items = list(data.items())
        if limit:
            items = items[:limit]
        
        for fastq_name, record in items:
            try:
                with transaction.atomic():
                    # Get the study set value and clean it
                    study_set_raw = record.get('Study Set', '')
                    study_set_value = clean_study_set(study_set_raw)
                    
                    # Create Metadata record with cleaned study set value
                    metadata = Metadata.objects.create(
                        fastq_name=fastq_name,
                        organism_name=record.get('Organism'),
                        library_prep_method_name=record.get('Library Prep Method'),
                        studies=study_set_value  # Store as clean string
                    )
                    metadata_count += 1
                    
                    # Create Main record
                    main = Main.objects.create(
                        fastq_name=metadata,
                        study_set=study_set_value,  # Use the same cleaned value
                        library_prep_method=record.get('Library Prep Method'),
                        organism=record.get('Organism'),
                        alignment_status=record.get('Alignment', 'NA'),
                        postqc_status=record.get('Post-Alignment', 'NA'),
                        ingest_status=record.get('Ingest', 'NA')
                    )
                    main_count += 1
                    
                    # Create LoadAssociation record
                    if 'Load Name' in record:
                        load_assoc = LoadAssociation.objects.create(
                            load_name=record['Load Name'],
                            fastq_name=metadata
                        )
                        load_association_count += 1
                    
                    # Create Alignment record
                    if 'Alignment' in record and record['Alignment'] != 'NA':
                        alignment = Alignment.objects.create(
                            fastq_name=metadata,
                            status_id=record['Alignment'],
                            start_time=parse_datetime(record.get('Alignment Time')),
                            end_time=parse_datetime(record.get('Alignment Time')),
                            fid=record.get('FID-Alignment')
                        )
                        alignment_count += 1
                    
                    # Create PostQC record
                    if 'Post-Alignment' in record and record['Post-Alignment'] != 'NA':
                        postqc = PostQC.objects.create(
                            fastq_name=metadata,
                            status_id=record['Post-Alignment'],
                            start_time=parse_datetime(record.get('Post Alignment Time')),
                            end_time=parse_datetime(record.get('Post Alignment Time')),
                            fid=record.get('FID-Post-Alignment')
                        )
                        postqc_count += 1
                    
                    # Create Ingest record
                    if 'Ingest' in record and record['Ingest'] != 'NA':
                        ingest = Ingest.objects.create(
                            fastq_name=metadata,
                            status_id=record['Ingest'],
                            start_time=parse_datetime(record.get('Ingest Time')),
                            end_time=parse_datetime(record.get('Ingest Time')),
                            fid=record.get('FID-Ingest')
                        )
                        ingest_count += 1
                    
                    records_processed += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing record {fastq_name}: {str(e)}'))
        
        self.stdout.write(f'Total records processed: {records_processed}')
        self.stdout.write(f'Metadata records: {metadata_count}')
        self.stdout.write(f'Main records: {main_count}')
        self.stdout.write(f'LoadAssociation records: {load_association_count}')
        self.stdout.write(f'Alignment records: {alignment_count}')
        self.stdout.write(f'PostQC records: {postqc_count}')
        self.stdout.write(f'Ingest records: {ingest_count}')