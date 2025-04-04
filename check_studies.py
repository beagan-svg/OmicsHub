import os
import sys
import django

# Set up Django environment
# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from viewer.models import Metadata

# Get the first record and print its studies field
record = Metadata.objects.first()
print(f"Studies field type: {type(record.studies)}")
print(f"Studies field value: {record.studies}") 