from django.core.management.base import BaseCommand
import os
import re

class Command(BaseCommand):
    help = 'Verify default column settings consistency across files'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Verifying Default Column Settings Consistency'))
        
        # Define the expected default column visibility settings
        expected_defaults = {
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
        
        # Get the path to the JavaScript file
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        js_file_path = os.path.join(project_root, 'viewer', 'static', 'viewer', 'js', 'column-toggle.js')
        
        # Read the JavaScript file
        try:
            with open(js_file_path, 'r') as f:
                js_content = f.read()
            
            # Extract the defaultColumnVisibility object from the JavaScript file
            js_defaults = {}
            default_section_match = re.search(r'const\s+defaultColumnVisibility\s*=\s*{([\s\S]*?)};', js_content)
            
            if default_section_match:
                default_section = default_section_match.group(1)
                # Parse each line to extract column names and values
                for line in default_section.strip().split('\n'):
                    line = line.strip()
                    if not line or line.startswith('//'):
                        continue
                    
                    parts = line.split(':')
                    if len(parts) >= 2:
                        column_name = parts[0].strip().strip("'").strip('"')
                        value_part = parts[1].strip().rstrip(',')
                        is_visible = value_part.lower() == 'true'
                        js_defaults[column_name] = is_visible
            
            # Compare the expected defaults with the JavaScript defaults
            all_columns = set(expected_defaults.keys()) | set(js_defaults.keys())
            
            inconsistencies = []
            for column in all_columns:
                expected = expected_defaults.get(column)
                actual = js_defaults.get(column)
                
                if expected is None:
                    inconsistencies.append(f"Column '{column}' defined in JS but not in expected defaults")
                elif actual is None:
                    inconsistencies.append(f"Column '{column}' defined in expected defaults but not in JS")
                elif expected != actual:
                    inconsistencies.append(f"Column '{column}' has different values: expected={expected}, actual={actual}")
            
            if inconsistencies:
                self.stdout.write(self.style.ERROR('Found inconsistencies in default column settings:'))
                for inconsistency in inconsistencies:
                    self.stdout.write(self.style.ERROR(f"- {inconsistency}"))
            else:
                self.stdout.write(self.style.SUCCESS('Default column settings are consistent across files!'))
                
                # Print the consistent default settings
                self.stdout.write(self.style.NOTICE('\nVerified Default Column Settings:'))
                self.stdout.write(self.style.SUCCESS('\nVisible columns:'))
                for column, is_visible in expected_defaults.items():
                    if is_visible:
                        self.stdout.write(f"- {column}")
                
                self.stdout.write(self.style.WARNING('\nHidden columns:'))
                for column, is_visible in expected_defaults.items():
                    if not is_visible:
                        self.stdout.write(f"- {column}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error verifying column settings: {str(e)}')) 