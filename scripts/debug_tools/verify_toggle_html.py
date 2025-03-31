#!/usr/bin/env python
"""
OCS Database - Toggle HTML Verification Tool

This script checks the HTML output of the application for proper column classes
and toggle functionality. It examines both the main page and debug page for
the presence of toggle elements, column classes, and JavaScript functions.

Usage:
    python scripts/debug_tools/verify_toggle_html.py

Output:
    A verification report showing:
    - Toggle elements found in the HTML
    - Table headers and cells with column classes
    - Presence of JavaScript functions for toggle functionality
    - Recommendations for fixing issues

Requirements:
    - Django server must be running
    - BeautifulSoup4 must be installed (pip install beautifulsoup4)
    - Requests must be installed (pip install requests)
"""

import os
import sys
import re
import requests
from bs4 import BeautifulSoup

def check_html_for_column_classes():
    """Check the HTML output for proper column classes and toggle functionality."""
    
    # Define URLs to check
    main_url = "http://localhost:8090/"
    debug_url = "http://localhost:8090/debug/toggles/"
    
    urls_to_check = [
        {"name": "Main Page", "url": main_url},
        {"name": "Debug Page", "url": debug_url}
    ]
    
    for url_info in urls_to_check:
        name = url_info["name"]
        url = url_info["url"]
        
        print(f"\n{'='*50}")
        print(f"Checking {name} ({url})")
        print(f"{'='*50}")
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check for toggle elements
                toggle_elements = soup.select('.toggle-switch')
                print(f"Toggle elements found: {len(toggle_elements)}")
                
                # Check if all toggle elements have data-field attribute
                toggle_with_data_field = [t for t in toggle_elements if t.get('data-field')]
                print(f"Toggle elements with data-field attribute: {len(toggle_with_data_field)}")
                
                # Check for table headers with column classes
                th_elements = soup.select('th[class*="column-"]')
                print(f"Table headers with column-* class: {len(th_elements)}")
                
                # Check for table cells with column classes
                td_elements = soup.select('td[class*="column-"]')
                print(f"Table cells with column-* class: {len(td_elements)}")
                
                # Get unique column classes
                column_classes = set()
                for el in soup.select('[class*="column-"]'):
                    for cls in el.get('class', []):
                        if cls.startswith('column-'):
                            column_classes.add(cls)
                
                print(f"Unique column classes found: {len(column_classes)}")
                if column_classes:
                    print("Column classes found:")
                    for cls in sorted(column_classes):
                        print(f"  - {cls}")
                
                # Check for toggleColumnVisibility function
                scripts = soup.find_all('script')
                toggle_function_found = False
                for script in scripts:
                    if script.string and 'toggleColumnVisibility' in script.string:
                        toggle_function_found = True
                        break
                
                print(f"toggleColumnVisibility function found: {toggle_function_found}")
                
                # Check if metadata-toggle.js is included
                toggle_js_found = False
                for script in soup.find_all('script'):
                    if script.get('src') and 'metadata-toggle.js' in script.get('src'):
                        toggle_js_found = True
                        break
                
                print(f"metadata-toggle.js included: {toggle_js_found}")
                
            else:
                print(f"Failed to get {name}: HTTP {response.status_code}")
        except Exception as e:
            print(f"Error checking {name}: {str(e)}")
    
    print("\n" + "="*50)
    print("RECOMMENDATIONS:")
    print("="*50)
    print("1. Make sure all toggle elements have the data-field attribute")
    print("2. Make sure all table header cells (<th>) have appropriate column-* classes")
    print("3. Make sure all table data cells (<td>) have appropriate column-* classes")
    print("4. Make sure the toggleColumnVisibility function is present and called on toggle changes")
    print("5. Check table.html to ensure it properly applies column-* classes")
    print("6. Check main_list.html to ensure toggle elements are correctly defined")
    print("7. Check that metadata-toggle.js is included and properly initializes toggle functionality")

if __name__ == "__main__":
    check_html_for_column_classes() 