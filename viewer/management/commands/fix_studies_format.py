import json
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from viewer.models import Metadata

class Command(BaseCommand):
    help = 'Fix the format of studies field in Metadata model from list to string'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be done without actually changing the database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write('Running in dry-run mode - no changes will be made')
        
        # Get all Metadata records
        metadata_records = Metadata.objects.all()
        total_records = metadata_records.count()
        
        self.stdout.write(f'Processing {total_records} metadata records...')
        
        # Stats
        stats = {
            'fixed_list': 0,
            'fixed_json_string': 0,
            'already_clean': 0,
            'empty': 0
        }
        
        # Process records in transaction batches for efficiency
        batch_size = 500
        for i in range(0, total_records, batch_size):
            batch = metadata_records[i:i+batch_size]
            
            if not dry_run:
                with transaction.atomic():
                    self._process_batch(batch, stats, dry_run=False)
            else:
                self._process_batch(batch, stats, dry_run=True)
            
            self.stdout.write(f'Processed {min(i + batch_size, total_records)}/{total_records} records')
        
        self.stdout.write(self.style.SUCCESS(f'Processing complete!'))
        self.stdout.write(f'Records converted from list: {stats["fixed_list"]}')
        self.stdout.write(f'Records with JSON formatting fixed: {stats["fixed_json_string"]}')
        self.stdout.write(f'Records already clean: {stats["already_clean"]}')
        self.stdout.write(f'Records empty: {stats["empty"]}')
    
    def _clean_json_string(self, value):
        """Clean a string that contains JSON formatting"""
        if not value:
            return value
            
        # Handle empty list case explicitly
        if value == '[]':
            return ''
        
        # First try to parse as JSON - this will handle most cases
        try:
            # Try to parse as JSON array
            parsed = json.loads(value)
            if isinstance(parsed, list):
                if len(parsed) > 0:
                    return parsed[0]
                else:
                    return ''  # Empty list case
            return value
        except json.JSONDecodeError:
            pass
        
        # If JSON parsing fails, try regex patterns
        # Remove outer brackets and quotes
        if value.startswith('["') and value.endswith('"]'):
            # Extract content between quotes
            match = re.match(r'\["([^"]+)"\]', value)
            if match:
                return match.group(1)
        
        # Try other patterns
        if value.startswith('[') and value.endswith(']'):
            # Remove brackets
            inside = value[1:-1].strip()
            # Remove quotes if present
            if inside.startswith('"') and inside.endswith('"'):
                inside = inside[1:-1]
            elif inside.startswith("'") and inside.endswith("'"):
                inside = inside[1:-1]
            return inside
        
        return value
    
    def _process_batch(self, batch, stats, dry_run=False):
        """Process a batch of metadata records"""
        for metadata in batch:
            studies_value = metadata.studies
            
            # Skip if None
            if studies_value is None:
                stats['empty'] += 1
                continue
                
            # Convert from list to string
            if isinstance(studies_value, list):
                if len(studies_value) > 0:
                    # Extract the first item from the list
                    new_value = studies_value[0] if studies_value[0] else ""
                    
                    if not dry_run:
                        metadata.studies = new_value
                        metadata.save(update_fields=['studies'])
                    else:
                        self.stdout.write(f'Would update list {metadata.fastq_name}: {studies_value} -> {new_value}')
                    
                    stats['fixed_list'] += 1
                else:
                    # Empty list
                    if not dry_run:
                        metadata.studies = ""
                        metadata.save(update_fields=['studies'])
                    else:
                        self.stdout.write(f'Would update empty list {metadata.fastq_name}: {studies_value} -> ""')
                    
                    stats['fixed_list'] += 1
            elif isinstance(studies_value, str):
                if studies_value == "":
                    stats['empty'] += 1
                    continue
                
                # Check if it's a JSON-formatted string that needs cleaning
                if ('[' in studies_value and ']' in studies_value) or ('"' in studies_value):
                    cleaned_value = self._clean_json_string(studies_value)
                    
                    if cleaned_value != studies_value:
                        if not dry_run:
                            metadata.studies = cleaned_value
                            metadata.save(update_fields=['studies'])
                        else:
                            self.stdout.write(f'Would clean JSON string {metadata.fastq_name}: {studies_value} -> {cleaned_value}')
                        
                        stats['fixed_json_string'] += 1
                    else:
                        stats['already_clean'] += 1
                else:
                    stats['already_clean'] += 1
            else:
                # Handle unexpected values
                if not dry_run:
                    metadata.studies = str(studies_value)
                    metadata.save(update_fields=['studies'])
                else:
                    self.stdout.write(f'Would convert {metadata.fastq_name}: {studies_value} -> {str(studies_value)}')
                
                stats['fixed_list'] += 1 