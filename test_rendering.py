#!/usr/bin/env python
import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'database_ocs_project.settings.development')
django.setup()

# Import models and tables
from viewer.models import Main
from viewer.tables import MainTable

def test_study_set_rendering():
    """Test how study_set values are rendered in the table"""
    print("Testing study set rendering in table...")
    
    # Get sample records
    samples = Main.objects.filter(study_set__isnull=False).exclude(study_set='')[:5]
    
    # Create table
    table = MainTable(samples)
    
    # Check rendering
    print("\nOriginal vs Rendered values:")
    print("-" * 80)
    print(f"{'FASTQ NAME':<20} | {'ORIGINAL VALUE':<30} | {'RENDERED VALUE':<30}")
    print("-" * 80)
    
    for row in table.rows:
        original = row.record.study_set
        rendered = table.render_study_set(original)
        print(f"{row.record.fastq_name_id:<20} | {original:<30} | {rendered:<30}")
    
    # Check all records for brackets or quotes
    all_samples = Main.objects.all()
    print(f"\nChecking all {all_samples.count()} records for brackets or quotes after rendering...")
    
    brackets_after = 0
    quotes_after = 0
    
    for sample in all_samples:
        rendered = table.render_study_set(sample.study_set)
        if rendered and ('[' in rendered or ']' in rendered):
            brackets_after += 1
        if rendered and ("'" in rendered or '"' in rendered):
            quotes_after += 1
    
    print(f"Records with brackets after rendering: {brackets_after}")
    print(f"Records with quotes after rendering: {quotes_after}")
    
    if brackets_after == 0 and quotes_after == 0:
        print("\nSuccess! All study_set values will display without brackets or quotes.")
    else:
        print("\nWarning! Some study_set values will still display with brackets or quotes.")

if __name__ == "__main__":
    test_study_set_rendering() 