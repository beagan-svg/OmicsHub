import django
from django.core.management.base import BaseCommand
from django.db.models import Q
from viewer.models import Main, Metadata, LoadAssociation
from viewer.filters import MainFilter

class Command(BaseCommand):
    help = 'Test the advanced filter functionality, particularly multi-select capabilities.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== TESTING ADVANCED FILTERS ==='))
        
        # Test multi-select organism filter
        self.test_multiselect_organism_filter()
        
        # Test multi-select status filters
        self.test_multiselect_status_filters()
        
        # Test combined filters
        self.test_combined_filters()
        
        self.stdout.write(self.style.SUCCESS('=== ADVANCED FILTER TESTING COMPLETE ==='))

    def test_multiselect_organism_filter(self):
        """Test multi-select organism filter"""
        self.stdout.write(self.style.NOTICE('\n=== Testing Multi-select Organism Filter ==='))
        
        # Get distinct organisms
        organisms = Main.objects.filter(
            organism__isnull=False
        ).exclude(organism='').values_list('organism', flat=True).distinct()
        
        organism_list = list(organisms)[:2]  # Use first two organisms for testing
        
        self.stdout.write(f"Testing organisms: {', '.join(organism_list)}")
        
        # Create filter with multiple organisms
        test_data = {
            'organism': organism_list
        }
        
        # Apply filter
        f = MainFilter(test_data, queryset=Main.objects.all())
        filtered_count = f.qs.count()
        
        # Get raw count for comparison
        raw_count = Main.objects.filter(
            organism__in=organism_list
        ).count()
        
        self.stdout.write(f"Filter returned {filtered_count} results")
        self.stdout.write(f"Raw query returned {raw_count} results")
        
        # They should match
        if filtered_count == raw_count:
            self.stdout.write(self.style.SUCCESS("Multi-select organism filter working correctly!"))
        else:
            self.stdout.write(self.style.ERROR("Multi-select organism filter not working as expected!"))
        
        # Show sample results
        if filtered_count > 0:
            self.stdout.write("Sample results:")
            for item in f.qs[:3]:
                self.stdout.write(f"- {item.fastq_name.fastq_name} ({item.organism})")

    def test_multiselect_status_filters(self):
        """Test multi-select status filters"""
        self.stdout.write(self.style.NOTICE('\n=== Testing Multi-select Status Filters ==='))
        
        # Get distinct alignment statuses
        alignment_statuses = Main.objects.filter(
            alignment_status__isnull=False
        ).exclude(alignment_status='').values_list('alignment_status', flat=True).distinct()
        
        status_list = list(alignment_statuses)[:2]  # Use first two statuses for testing
        
        self.stdout.write(f"Testing alignment statuses: {', '.join(status_list)}")
        
        # Create filter with multiple alignment statuses
        test_data = {
            'alignment_status': status_list
        }
        
        # Apply filter
        f = MainFilter(test_data, queryset=Main.objects.all())
        filtered_count = f.qs.count()
        
        # Get raw count for comparison
        raw_count = Main.objects.filter(
            alignment_status__in=status_list
        ).count()
        
        self.stdout.write(f"Filter returned {filtered_count} results")
        self.stdout.write(f"Raw query returned {raw_count} results")
        
        # They should match
        if filtered_count == raw_count:
            self.stdout.write(self.style.SUCCESS("Multi-select status filter working correctly!"))
        else:
            self.stdout.write(self.style.ERROR("Multi-select status filter not working as expected!"))
        
        # Show sample results
        if filtered_count > 0:
            self.stdout.write("Sample results:")
            for item in f.qs[:3]:
                self.stdout.write(f"- {item.fastq_name.fastq_name} ({item.alignment_status})")

    def test_combined_filters(self):
        """Test combining multiple filter types"""
        self.stdout.write(self.style.NOTICE('\n=== Testing Combined Filters ==='))
        
        # Get some organisms and statuses for testing
        organisms = list(Main.objects.filter(
            organism__isnull=False
        ).exclude(organism='').values_list('organism', flat=True).distinct()[:2])
        
        lib_prep_methods = list(Main.objects.filter(
            library_prep_method__isnull=False
        ).exclude(library_prep_method='').values_list('library_prep_method', flat=True).distinct()[:2])
        
        # Create filter with multiple criteria
        test_data = {
            'organism': organisms,
            'library_prep_method': lib_prep_methods
        }
        
        self.stdout.write(f"Testing combined filter:")
        self.stdout.write(f"- Organisms: {', '.join(organisms)}")
        self.stdout.write(f"- Library Prep Methods: {', '.join(lib_prep_methods)}")
        
        # Apply filter
        f = MainFilter(test_data, queryset=Main.objects.all())
        filtered_count = f.qs.count()
        
        # Get raw count for comparison (this should use OR logic between categories)
        raw_count = Main.objects.filter(
            organism__in=organisms,
            library_prep_method__in=lib_prep_methods
        ).count()
        
        self.stdout.write(f"Filter returned {filtered_count} results")
        self.stdout.write(f"Raw query returned {raw_count} results")
        
        # They should match
        if filtered_count == raw_count:
            self.stdout.write(self.style.SUCCESS("Combined filters working correctly!"))
        else:
            self.stdout.write(self.style.ERROR("Combined filters not working as expected!"))
        
        # Show sample results
        if filtered_count > 0:
            self.stdout.write("Sample results:")
            for item in f.qs[:5]:
                self.stdout.write(f"- {item.fastq_name.fastq_name} (Organism: {item.organism}, Lib Prep: {item.library_prep_method})") 