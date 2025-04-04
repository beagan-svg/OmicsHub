import os
import django
from django.conf import settings

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from viewer.models import Main, LoadAssociation, Metadata

def test_load_name_display():
    print("\n=== Testing Load Name Display ===\n")
    
    # Test 1: Check LoadAssociation records
    print("Test 1: Checking LoadAssociation records")
    load_associations = LoadAssociation.objects.all()
    print(f"Total LoadAssociation records: {load_associations.count()}")
    
    if load_associations.exists():
        print("\nFirst 5 LoadAssociation records:")
        for la in load_associations[:5]:
            print(f"- Fastq Name: {la.fastq_name}, Load Name: {la.load_name}")
    else:
        print("No LoadAssociation records found!")
    
    # Test 2: Check Main records and their load names
    print("\nTest 2: Checking Main records and their load names")
    main_records = Main.objects.all()
    print(f"Total Main records: {main_records.count()}")
    
    if main_records.exists():
        print("\nFirst 5 Main records and their load names:")
        for main in main_records[:5]:
            print(f"\nMain record: {main.fastq_name}")
            try:
                load_assoc = LoadAssociation.objects.get(fastq_name=main.fastq_name)
                print(f"  Load Name: {load_assoc.load_name}")
            except LoadAssociation.DoesNotExist:
                print("  No LoadAssociation found!")
    else:
        print("No Main records found!")
    
    # Test 3: Check access through Main -> Metadata -> LoadAssociation
    print("\nTest 3: Checking access through Main -> Metadata -> LoadAssociation")
    if main_records.exists():
        print("\nFirst 5 Main records and their load names through relationships:")
        for main in main_records[:5]:
            print(f"\nMain record: {main.fastq_name}")
            try:
                metadata = Metadata.objects.get(fastq_name=main.fastq_name)
                load_assoc = LoadAssociation.objects.get(fastq_name=main.fastq_name)
                print(f"  Load Name: {load_assoc.load_name}")
            except (Metadata.DoesNotExist, LoadAssociation.DoesNotExist) as e:
                print(f"  Error: {str(e)}")
    else:
        print("No Main records found!")

if __name__ == '__main__':
    test_load_name_display() 