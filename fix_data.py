from viewer.models import Metadata, Alignment, PostQC, Ingest, LoadAssociation, Main
import json
from datetime import datetime

def parse_datetime(datetime_str):
    if datetime_str == "NA":
        return None
    try:
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None

def fix_data():
    # Read all records from study.json
    json_path = '/allen/programs/celltypes/workgroups/rnaseqanalysis/bnguy/Projects/ocs/batch_csv/study.json'
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Process all records
    items = list(data.items())
    count = 0
    processed_count = 0
    errors = 0
    
    for fastq_name, item_data in items:
        try:
            # Get metadata
            try:
                metadata = Metadata.objects.get(fastq_name=fastq_name)
            except Metadata.DoesNotExist:
                # Skip if metadata doesn't exist
                continue
            
            # Create alignment record if data exists
            alignment_status = item_data.get('Alignment')
            if alignment_status:
                alignment, created = Alignment.objects.get_or_create(
                    fastq_name=metadata,
                    defaults={
                        'status_id': alignment_status,
                        'start_time': parse_datetime(item_data.get('Alignment Time')),
                        'fid': item_data.get('FID-Alignment', '')
                    }
                )
            
            # Create ingest record if data exists
            ingest_status = item_data.get('Ingest')
            if ingest_status:
                ingest, created = Ingest.objects.get_or_create(
                    fastq_name=metadata,
                    defaults={
                        'status_id': ingest_status,
                        'start_time': parse_datetime(item_data.get('Ingest Time')),
                        'fid': item_data.get('FID-Ingest', '')
                    }
                )
            
            # Create post-alignment QC record if data exists
            postqc_status = item_data.get('Post-Alignment')
            if postqc_status and postqc_status != 'NA':
                postqc, created = PostQC.objects.get_or_create(
                    fastq_name=metadata,
                    defaults={
                        'status_id': postqc_status,
                        'start_time': parse_datetime(item_data.get('Post Alignment Time')),
                        'fid': item_data.get('FID-Post-Alignment', '')
                    }
                )
            
            processed_count += 1
            if processed_count % 100 == 0:
                print(f"Processed {processed_count} records")
        
        except Exception as e:
            errors += 1
            if errors < 10:  # Only show the first few errors
                print(f"Error processing {fastq_name}: {e}")
        
        count += 1
    
    # Print final counts
    print("\nFinal counts:")
    print(f"Total records in JSON: {count}")
    print(f"Successfully processed: {processed_count}")
    print(f"Errors: {errors}")
    print(f"Metadata records: {Metadata.objects.count()}")
    print(f"Main records: {Main.objects.count()}")
    print(f"LoadAssociation records: {LoadAssociation.objects.count()}")
    print(f"Alignment records: {Alignment.objects.count()}")
    print(f"PostQC records: {PostQC.objects.count()}")
    print(f"Ingest records: {Ingest.objects.count()}")

fix_data() 