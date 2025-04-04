import os
import sys
import django

# Set up Django environment
# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from viewer.models import Metadata, Main, LoadAssociation, Alignment, PostQC, Ingest

# Print record counts
print("\nRecord Counts:")
print(f"Metadata records: {Metadata.objects.count()}")
print(f"Main records: {Main.objects.count()}")
print(f"LoadAssociation records: {LoadAssociation.objects.count()}")
print(f"Alignment records: {Alignment.objects.count()}")
print(f"PostQC records: {PostQC.objects.count()}")
print(f"Ingest records: {Ingest.objects.count()}")

# Check a sample record
sample = Metadata.objects.first()
print("\nSample Record:")
print(f"FASTQ Name: {sample.fastq_name}")
print(f"Studies: {sample.studies}")
print(f"Organism: {sample.organism_name}") 