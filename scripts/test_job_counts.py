#!/usr/bin/env python3
import os
import sys
import json
import glob
from bs4 import BeautifulSoup
import requests
import subprocess
from pathlib import Path
import django

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from viewer.models import Alignment, PostQC

def check_database_running_jobs():
    """Check number of running jobs in database"""
    print("\nChecking database running jobs...")
    running_alignments = Alignment.objects.filter(status_id='IN_PROGRESS').count()
    running_postqc = PostQC.objects.filter(status_id='IN_PROGRESS').count()
    total_running = running_alignments + running_postqc
    print(f"Found {running_alignments} running alignment jobs")
    print(f"Found {running_postqc} running post-QC jobs")
    print(f"Total: {total_running} running jobs in database")
    return total_running

def check_webpage_running_jobs():
    """Check number of running jobs from web page"""
    print("\nChecking web page running jobs...")
    urls = [
        'http://0.0.0.0:8085/pipeline/jobs/',
    ]
    
    for url in urls:
        print(f"\nTrying URL: {url}")
        try:
            response = requests.get(url)
            print(f"Got {response.status_code} response")
            
            if response.status_code == 200:
                # Save the HTML for debugging
                with open('debug_page.html', 'w') as f:
                    f.write(response.text)
                print("Saved HTML to debug_page.html")
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check statistics section
                print("\nChecking statistics section:")
                stats_section = soup.find('div', class_='card-body').find_all('h2')
                if stats_section and len(stats_section) >= 2:
                    alignment_jobs = int(stats_section[0].text.strip())
                    postqc_jobs = int(stats_section[1].text.strip())
                    total_stats = alignment_jobs + postqc_jobs
                    print(f"Statistics show: {alignment_jobs} alignment jobs, {postqc_jobs} post-QC jobs (Total: {total_stats})")
                
                # Check running jobs section
                print("\nChecking running jobs section:")
                running_section = soup.find('h5', string=lambda text: text and 'Running Jobs' in text)
                if running_section:
                    badge = running_section.find('span', class_='badge')
                    if badge:
                        running_count = int(badge.text.strip())
                        print(f"Running jobs badge shows: {running_count} jobs")
                    
                    # Check if "No jobs" message exists
                    no_jobs_msg = soup.find('div', class_='alert-info', string=lambda text: text and 'No jobs are currently running' in text)
                    if no_jobs_msg:
                        print("Found 'No jobs running' message")
                        running_count = 0
                else:
                    # If we can't find the running jobs section, assume 0
                    running_count = 0
                    print("Could not find running jobs section, assuming 0 running jobs")
                
                return {
                    'stats_total': total_stats if 'total_stats' in locals() else None,
                    'badge_count': running_count if 'running_count' in locals() else 0
                }
                
        except requests.RequestException as e:
            print(f"Error accessing {url}: {str(e)}")
            continue
        except Exception as e:
            print(f"Error parsing page: {str(e)}")
            continue
    
    print("\nNone of the URLs worked")
    return None

def main():
    print("\nChecking job counts in different places...")
    print("=" * 50)
    
    db_count = check_database_running_jobs()
    web_counts = check_webpage_running_jobs()
    
    print("\nSummary:")
    print("=" * 50)
    print(f"Database running jobs: {db_count}")
    if web_counts:
        if web_counts['stats_total'] is not None:
            print(f"Web page statistics total: {web_counts['stats_total']}")
        if web_counts['badge_count'] is not None:
            print(f"Web page badge count: {web_counts['badge_count']}")
        
        # Check for discrepancies
        if web_counts['stats_total'] != web_counts['badge_count']:
            print("\nWARNING: Discrepancy between statistics and badge count!")
        if db_count != web_counts['badge_count']:
            print("\nWARNING: Discrepancy between database and web page badge count!")
        if db_count != web_counts['stats_total']:
            print("\nWARNING: Discrepancy between database and web page statistics!")
    print("=" * 50)

if __name__ == '__main__':
    main() 