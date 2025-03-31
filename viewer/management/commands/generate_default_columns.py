from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import json

class Command(BaseCommand):
    help = 'Generate JavaScript for manually setting the default column visibility'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Default Column Settings Generator'))
        
        # Default column visibility settings
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
        
        # Generate JavaScript code to set default column visibility
        js_code = """
// Copy and paste this into your browser's developer console to set default column visibility

// First, clear any existing column visibility settings
localStorage.removeItem('columnsInitialized');

// Convert snake_case to camelCase
function toCamelCase(str) {
    return str.split('_').map((word, index) => {
        return index === 0 ? word : word.charAt(0).toUpperCase() + word.slice(1);
    }).join('');
}

// Set default column visibility
const defaultColumns = {
"""
        
        # Add each column to the JavaScript code
        for column, is_visible in default_columns.items():
            js_code += f"    '{column}': {str(is_visible).lower()},\n"
        
        # Close the JavaScript object and add the rest of the code
        js_code += """};

// Set localStorage values for each column
Object.keys(defaultColumns).forEach(column => {
    const storageKey = `show${toCamelCase(column)}`;
    localStorage.setItem(storageKey, defaultColumns[column]);
});

// Mark as initialized
localStorage.setItem('columnsInitialized', 'true');

console.log('Default column visibility settings applied. Please refresh the page.');
        """
        
        self.stdout.write(self.style.NOTICE('\nInstructions:'))
        self.stdout.write('1. Open your browser\'s developer tools (F12 or Ctrl+Shift+I)')
        self.stdout.write('2. Navigate to the "Console" tab')
        self.stdout.write('3. Copy and paste the following JavaScript code:')
        self.stdout.write(self.style.WARNING(js_code))
        self.stdout.write('4. Press Enter to execute the code')
        self.stdout.write('5. Refresh the page to see the default column settings applied')
        
        self.stdout.write(self.style.SUCCESS('\nCode generated successfully')) 