import os
import sys
import django

# Set up Django environment
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from database_ocs.models import Metadata

# Get the first record and print its studies field
record = Metadata.objects.first()
print(f"Studies field type: {type(record.studies)}")
print(f"Studies field value: {record.studies}") 