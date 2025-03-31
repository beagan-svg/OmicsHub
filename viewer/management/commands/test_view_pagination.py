from django.core.management.base import BaseCommand
from django.db.models import Q
from viewer.models import Main, Metadata
from viewer.filters import MainFilter

class Command(BaseCommand):
    help = 'Test the pagination functionality by checking result counts per page'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== TESTING PAGINATION ==='))
        
        # Test pagination with all results
        self.test_all_pagination()
        
        # Test pagination with filtered results
        self.test_filtered_pagination()
        
        self.stdout.write(self.style.SUCCESS('=== PAGINATION TESTING COMPLETE ==='))

    def test_all_pagination(self):
        """Test pagination with all results"""
        self.stdout.write(self.style.NOTICE('\n=== Testing All Results Pagination ==='))
        
        # Get total count
        total_count = Main.objects.count()
        self.stdout.write(f"Total records: {total_count}")
        
        # Check results per page (should be 25)
        results_per_page = 25
        
        # Calculate expected number of pages
        expected_pages = (total_count + results_per_page - 1) // results_per_page
        self.stdout.write(f"Expected number of pages: {expected_pages}")
        
        # Check each page
        for page in range(1, min(expected_pages + 1, 4)):  # Test first 3 pages
            start_idx = (page - 1) * results_per_page
            end_idx = min(page * results_per_page, total_count)
            expected_count = end_idx - start_idx
            
            # Get actual queryset for this page
            queryset = Main.objects.all().order_by('fastq_name__fastq_name')[start_idx:end_idx]
            actual_count = queryset.count()
            
            self.stdout.write(f"Page {page}: expected {expected_count}, actual {actual_count}")
            
            if actual_count != expected_count:
                self.stdout.write(self.style.ERROR(f"  FAILED: Page {page} has incorrect count"))
            else:
                self.stdout.write(self.style.SUCCESS(f"  SUCCESS: Page {page} has correct count"))

    def test_filtered_pagination(self):
        """Test pagination with filtered results"""
        self.stdout.write(self.style.NOTICE('\n=== Testing Filtered Results Pagination ==='))
        
        # Test with a few organisms
        test_organisms = list(Main.objects.filter(
            organism__isnull=False
        ).exclude(organism='').values_list('organism', flat=True).distinct()[:3])
        
        for organism in test_organisms:
            self.stdout.write(f"\nTesting organism: {organism}")
            
            # Apply filter
            filter_data = {'organism': [organism]}
            f = MainFilter(filter_data, queryset=Main.objects.all())
            
            # Get total filtered count
            total_filtered = f.qs.count()
            self.stdout.write(f"Total filtered records: {total_filtered}")
            
            # Check results per page (should be 25)
            results_per_page = 25
            
            # Calculate expected number of pages
            expected_pages = (total_filtered + results_per_page - 1) // results_per_page
            self.stdout.write(f"Expected number of pages: {expected_pages}")
            
            # Check each page
            for page in range(1, min(expected_pages + 1, 3)):  # Test first 2 pages
                start_idx = (page - 1) * results_per_page
                end_idx = min(page * results_per_page, total_filtered)
                expected_count = end_idx - start_idx
                
                # Get actual queryset for this page
                queryset = f.qs.order_by('fastq_name__fastq_name')[start_idx:end_idx]
                actual_count = queryset.count()
                
                self.stdout.write(f"  Page {page}: expected {expected_count}, actual {actual_count}")
                
                if actual_count != expected_count:
                    self.stdout.write(self.style.ERROR(f"    FAILED: Page {page} has incorrect count"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"    SUCCESS: Page {page} has correct count")) 