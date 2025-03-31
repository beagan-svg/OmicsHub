from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

class Command(BaseCommand):
    help = 'Generate JavaScript code to reset column visibility settings in browser localStorage'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Column Settings Reset Tool'))
        
        # Generate JavaScript code to clear localStorage column settings
        js_code = """
// Copy and paste this into your browser's developer console to reset column settings

// First, clear all column visibility settings
const columnPrefixes = ['show', 'column', 'toggle'];
const columnKeys = ['columnsInitialized', 'allColumnsVisible'];
const columnNames = [
    'fastq_name', 'study_set', 'load_name', 'library_prep_method', 
    'organism_common_name', 'ingest_status', 'alignment_status', 'postqc_status',
    'batch_name', 'batch_name_from_vendor', 'cell_capture', 'sample_id',
    'amplification_name', 'amplification_id', 'cell_prep_type', 
    'sequencing_vendor', 'alignment_method', 'library_prep_method_id', 
    'library_prep_name'
];

// Convert snake_case to camelCase
function toCamelCase(str) {
    return str.split('_').map((word, index) => {
        return index === 0 ? word : word.charAt(0).toUpperCase() + word.slice(1);
    }).join('');
}

// Clear all possible column-related settings
for (const prefix of columnPrefixes) {
    for (const name of columnNames) {
        // Try different key formats
        const snakeKey = `${prefix}${name}`;
        const camelKey = `${prefix}${toCamelCase(name)}`;
        localStorage.removeItem(snakeKey);
        localStorage.removeItem(camelKey);
    }
}

// Clear special keys
for (const key of columnKeys) {
    localStorage.removeItem(key);
}

console.log('Column settings cleared! Refresh the page to see default columns.');
        """
        
        self.stdout.write(self.style.NOTICE('\nReset Instructions:'))
        self.stdout.write('1. Open your browser\'s developer tools (F12 or Ctrl+Shift+I)')
        self.stdout.write('2. Navigate to the "Console" tab')
        self.stdout.write('3. Copy and paste the following JavaScript code:')
        self.stdout.write(self.style.WARNING(js_code))
        self.stdout.write('4. Press Enter to execute the code')
        self.stdout.write('5. Refresh the page to see the default column settings applied')
        
        self.stdout.write(self.style.SUCCESS('\nReset tool generated successfully')) 