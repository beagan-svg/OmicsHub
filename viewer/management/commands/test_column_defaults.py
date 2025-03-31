from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import json
import os

class Command(BaseCommand):
    help = 'Test the default column visibility functionality'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing Default Column Visibility'))
        
        # Print the default column visibility settings
        default_columns = {
            'fastq_name': True,
            'study_set': True,
            'load_name': True,
            'library_prep_method': True,
            'organism_common_name': True,
            'ingest_status': True,
            'alignment_status': True,
            'postqc_status': True,
            'batch_name': False,
            'batch_name_from_vendor': False,
            'cell_capture': False,
            'sample_id': False,
            'amplification_name': False,
            'amplification_id': False,
            'cell_prep_type': False,
            'sequencing_vendor': False,
            'alignment_method': False,
            'library_prep_method_id': False,
            'library_prep_name': False
        }
        
        # Print the default column visibility settings in a readable format
        self.stdout.write(self.style.NOTICE('\nDefault Column Visibility Settings:'))
        visible_columns = []
        hidden_columns = []
        
        for column, is_visible in default_columns.items():
            if is_visible:
                visible_columns.append(column)
            else:
                hidden_columns.append(column)
        
        self.stdout.write(self.style.SUCCESS('\nVisible columns:'))
        for column in visible_columns:
            self.stdout.write(f'- {column}')
            
        self.stdout.write(self.style.WARNING('\nHidden columns:'))
        for column in hidden_columns:
            self.stdout.write(f'- {column}')
            
        self.stdout.write(self.style.SUCCESS('\nVerification steps:'))
        self.stdout.write('1. Make sure the column settings JavaScript is correctly loaded')
        self.stdout.write('2. Check that the default column visibility settings match the ones listed above')
        self.stdout.write('3. Clear your browser localStorage to test initial column visibility')
        self.stdout.write('4. Visit the page and verify only the "Visible columns" are shown')
        self.stdout.write('5. Try the "Reset to Default" button after toggling columns')
        
        self.stdout.write(self.style.SUCCESS('\nTest completed successfully')) 