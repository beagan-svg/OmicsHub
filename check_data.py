#!/usr/bin/env python
from scripts.utilities.db_utils import setup_django_env
setup_django_env()
from viewer.models import Metadata, Main

print(f'Total Metadata records: {Metadata.objects.count()}')
print(f'Total Main records: {Main.objects.count()}')
print('Sample records:')
for record in Metadata.objects.all()[:5]:
    print(f' - {record.fastq_name}: {record.studies}')
    
    # Get corresponding Main record
    try:
        main = Main.objects.get(fastq_name=record)
        print(f'   Status: Alignment={main.alignment_status}, PostQC={main.postqc_status}, Ingest={main.ingest_status}')
    except Main.DoesNotExist:
        print('   No Main record found') 