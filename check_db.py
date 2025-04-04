import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'database_ocs_project.settings.development')
django.setup()

from viewer.models import Metadata

# Get the first record and print its studies field
record = Metadata.objects.first()
if record:
    print(f"Studies field value: {record.studies}")
    print(f"Studies field type: {type(record.studies)}")
else:
    print("No records found in the metadata table.") 