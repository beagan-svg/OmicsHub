import django
from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from viewer.models import Main, Metadata, LoadAssociation
from viewer.filters import MainFilter

class Command(BaseCommand):
    help = 'Test the filter functionality to ensure there are no duplicate results'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== TESTING FILTER FOR DUPLICATES ==='))
        
        # Test search filter for duplicates
        self.test_search_filter_duplicates()
        
        # Test load_name filter for duplicates
        self.test_load_name_filter_duplicates()
        
        # Test combined filters for duplicates
        self.test_combined_filters_duplicates()
        
        self.stdout.write(self.style.SUCCESS('=== DUPLICATE FILTER TESTING COMPLETE ==='))

    def test_search_filter_duplicates(self):
        """Test search filter for duplicate results"""
        self.stdout.write(self.style.NOTICE('\n=== Testing Search Filter for Duplicates ==='))
        
        # Test with a search term that would match across multiple related objects
        search_term = '10X'  # Common term that might appear in many records
        
        self.stdout.write(f"Testing search term: '{search_term}'")
        
        # Apply filter
        f = MainFilter({'search': search_term}, queryset=Main.objects.all())
        filtered_results = list(f.qs)
        
        # Check for duplicates by comparing IDs
        result_ids = [item.fastq_name.fastq_name for item in filtered_results]
        unique_ids = set(result_ids)
        
        self.stdout.write(f"Total results: {len(filtered_results)}")
        self.stdout.write(f"Unique results: {len(unique_ids)}")
        
        # They should match (no duplicates)
        if len(filtered_results) == len(unique_ids):
            self.stdout.write(self.style.SUCCESS("Search filter produces no duplicates!"))
        else:
            self.stdout.write(self.style.ERROR(f"Search filter produced {len(filtered_results) - len(unique_ids)} duplicate results!"))
            
            # Identify the duplicates
            duplicate_counts = {}
            for item_id in result_ids:
                duplicate_counts[item_id] = duplicate_counts.get(item_id, 0) + 1
            
            duplicates = {k: v for k, v in duplicate_counts.items() if v > 1}
            self.stdout.write(f"Duplicated items: {duplicates}")

    def test_load_name_filter_duplicates(self):
        """Test load_name filter for duplicate results"""
        self.stdout.write(self.style.NOTICE('\n=== Testing Load Name Filter for Duplicates ==='))
        
        # Get a load name that exists in the database
        load_assoc = LoadAssociation.objects.first()
        if not load_assoc:
            self.stdout.write(self.style.WARNING("No load associations found, skipping test"))
            return
            
        load_name = load_assoc.load_name
        self.stdout.write(f"Testing load_name: '{load_name}'")
        
        # Apply filter
        f = MainFilter({'load_name': load_name}, queryset=Main.objects.all())
        filtered_results = list(f.qs)
        
        # Check for duplicates by comparing IDs
        result_ids = [item.fastq_name.fastq_name for item in filtered_results]
        unique_ids = set(result_ids)
        
        self.stdout.write(f"Total results: {len(filtered_results)}")
        self.stdout.write(f"Unique results: {len(unique_ids)}")
        
        # They should match (no duplicates)
        if len(filtered_results) == len(unique_ids):
            self.stdout.write(self.style.SUCCESS("Load name filter produces no duplicates!"))
        else:
            self.stdout.write(self.style.ERROR(f"Load name filter produced {len(filtered_results) - len(unique_ids)} duplicate results!"))
            
            # Identify the duplicates
            duplicate_counts = {}
            for item_id in result_ids:
                duplicate_counts[item_id] = duplicate_counts.get(item_id, 0) + 1
            
            duplicates = {k: v for k, v in duplicate_counts.items() if v > 1}
            self.stdout.write(f"Duplicated items: {duplicates}")

    def test_combined_filters_duplicates(self):
        """Test combined filters for duplicate results"""
        self.stdout.write(self.style.NOTICE('\n=== Testing Combined Filters for Duplicates ==='))
        
        # Get some organisms and statuses for testing
        organisms = list(Main.objects.filter(
            organism__isnull=False
        ).exclude(organism='').values_list('organism', flat=True).distinct()[:2])
        
        lib_prep_methods = list(Main.objects.filter(
            library_prep_method__isnull=False
        ).exclude(library_prep_method='').values_list('library_prep_method', flat=True).distinct()[:2])
        
        # Add a search term to make it more complex
        search_term = '10X'
        
        # Create combined filter
        test_data = {
            'search': search_term,
            'organism': organisms,
            'library_prep_method': lib_prep_methods
        }
        
        self.stdout.write(f"Testing combined filter:")
        self.stdout.write(f"- Search term: '{search_term}'")
        self.stdout.write(f"- Organisms: {', '.join(organisms)}")
        self.stdout.write(f"- Library Prep Methods: {', '.join(lib_prep_methods)}")
        
        # Apply filter
        f = MainFilter(test_data, queryset=Main.objects.all())
        filtered_results = list(f.qs)
        
        # Check for duplicates by comparing IDs
        result_ids = [item.fastq_name.fastq_name for item in filtered_results]
        unique_ids = set(result_ids)
        
        self.stdout.write(f"Total results: {len(filtered_results)}")
        self.stdout.write(f"Unique results: {len(unique_ids)}")
        
        # They should match (no duplicates)
        if len(filtered_results) == len(unique_ids):
            self.stdout.write(self.style.SUCCESS("Combined filters produce no duplicates!"))
        else:
            self.stdout.write(self.style.ERROR(f"Combined filters produced {len(filtered_results) - len(unique_ids)} duplicate results!"))
            
            # Identify the duplicates
            duplicate_counts = {}
            for item_id in result_ids:
                duplicate_counts[item_id] = duplicate_counts.get(item_id, 0) + 1
            
            duplicates = {k: v for k, v in duplicate_counts.items() if v > 1}
            self.stdout.write(f"Duplicated items: {duplicates}") 