from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.test.client import RequestFactory
from viewer.models import Main
from viewer.tables import MainTable
from django.http import HttpResponse
from bs4 import BeautifulSoup
import re

class Command(BaseCommand):
    help = 'Check HTML structure of rendered table headers to diagnose column visibility issues'

    def handle(self, *args, **options):
        try:
            # Create a sample request
            factory = RequestFactory()
            request = factory.get('/')
            
            # Get some sample data
            sample_data = Main.objects.all()[:10]
            
            # Create the table
            table = MainTable(sample_data)
            
            # Render the table
            table_html = table.as_html(request)
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(table_html, 'html.parser')
            
            # Extract table headers
            headers = soup.find_all('th')
            
            self.stdout.write("\n=== TABLE HEADER ANALYSIS ===\n")
            self.stdout.write(f"Found {len(headers)} table headers\n")
            
            # Display header details
            for idx, header in enumerate(headers):
                header_text = header.get_text(strip=True)
                header_class = header.get('class', [])
                header_id = header.get('id', 'No ID')
                
                self.stdout.write(f"Header {idx+1}: '{header_text}'")
                self.stdout.write(f"  - Class: {' '.join(header_class)}")
                self.stdout.write(f"  - ID: {header_id}")
                self.stdout.write(f"  - HTML: {header}")
                self.stdout.write("")
                
            # Check for timestamp-related headers
            timestamp_headers = [h for h in headers if any(t in h.get_text(strip=True).lower() for t in ('start', 'end', 'time'))]
            self.stdout.write("\n=== TIMESTAMP HEADERS ===\n")
            self.stdout.write(f"Found {len(timestamp_headers)} timestamp-related headers\n")
            
            for idx, header in enumerate(timestamp_headers):
                header_text = header.get_text(strip=True)
                header_class = header.get('class', [])
                
                self.stdout.write(f"Timestamp Header {idx+1}: '{header_text}'")
                self.stdout.write(f"  - Class: {' '.join(header_class)}")
                self.stdout.write("")
                
            # Check JavaScript column ID pattern
            js_column_pattern = re.compile(r'column[_-](\w+)')
            
            # Extract expected JS IDs for each header
            self.stdout.write("\n=== JS COLUMN IDENTIFIER MAPPING ===\n")
            for idx, header in enumerate(headers):
                header_text = header.get_text(strip=True).lower()
                header_class = ' '.join(header.get('class', []))
                
                # Extract column name from class
                match = js_column_pattern.search(header_class)
                column_id = match.group(1) if match else 'unknown'
                
                expected_js_id = f"column_{header_text.lower().replace(' ', '_')}"
                toggle_id = f"toggle{column_id.replace('_', ' ').title().replace(' ', '')}"
                
                self.stdout.write(f"Header: '{header_text}'")
                self.stdout.write(f"  - Actual class ID: column_{column_id}")
                self.stdout.write(f"  - Expected toggle ID: {toggle_id}")
                self.stdout.write("")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error analyzing table: {str(e)}")) 