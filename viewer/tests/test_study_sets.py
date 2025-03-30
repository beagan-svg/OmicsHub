import os
import django
import sys

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ocs.settings')
django.setup()

from viewer.models import Metadata

def test_study_sets():
    print("\nTesting Study Sets in Database:")
    print("-" * 50)
    
    # Get all unique study sets
    study_sets = Metadata.objects.filter(
        studies__isnull=False
    ).values_list('studies', flat=True).distinct().order_by('studies')
    
    print(f"Total unique study sets: {study_sets.count()}")
    print("\nFirst 5 study sets:")
    for study_set in study_sets[:5]:
        print(f"- {study_set}")
    
    # Check a specific study set count
    test_set = "P56_Unbiased_Sampling"
    count = Metadata.objects.filter(studies=test_set).count()
    print(f"\nCount of records with study set '{test_set}': {count}")

if __name__ == "__main__":
    test_study_sets() 