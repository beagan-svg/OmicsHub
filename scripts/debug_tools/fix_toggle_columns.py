#!/usr/bin/env python
"""
OCS Database - Toggle Column Fixer

This script fixes issues with toggle column functionality by updating the table.html
template to properly include column classes in the rendered table cells. It works
by modifying the Django template to ensure CSS classes from column definitions
are applied to both header and data cells.

Usage:
    python scripts/debug_tools/fix_toggle_columns.py

Features:
    - Backs up existing template files before modification
    - Updates table.html template to properly apply column classes
    - Verifies the presence of necessary JavaScript functions
    - Reports on changes made

Requirements:
    - Django environment must be properly configured
"""

import os
import sys
import re
import shutil
import datetime

# Set up Django environment
# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    import django
    django.setup()
except ImportError:
    print("Django not found. Make sure it's installed and the environment is set up correctly.")
    sys.exit(1)

def backup_file(file_path):
    """Create a backup of the specified file."""
    if os.path.exists(file_path):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{file_path}.bak_{timestamp}"
        shutil.copy2(file_path, backup_path)
        print(f"Backup created: {backup_path}")
        return True
    else:
        print(f"File not found: {file_path}")
        return False

def fix_table_template():
    """Fix the table.html template to properly apply column classes."""
    template_path = "viewer/templates/django_tables2/table.html"
    
    if not os.path.exists(template_path):
        # Try another common location
        template_path = "viewer/templates/viewer/table.html"
        if not os.path.exists(template_path):
            print("Table template not found. Please specify the correct path.")
            return False
    
    print(f"Working with template: {template_path}")
    
    # Backup the template
    if not backup_file(template_path):
        return False
    
    with open(template_path, 'r') as file:
        content = file.read()
    
    # Check if the template already includes column classes
    th_pattern = r'<th\s+(?:[^>]*\s+)?class\s*=\s*"(?:[^"]*\s+)?{{ column\.attrs\.th\.class }}'
    td_pattern = r'<td\s+(?:[^>]*\s+)?class\s*=\s*"(?:[^"]*\s+)?{{ column\.attrs\.td\.class }}'
    
    if re.search(th_pattern, content) and re.search(td_pattern, content):
        print("Template already includes column classes for th and td elements.")
        return True
    
    # Fix for th elements (column headers)
    th_replace_pattern = r'(<th\s+(?:[^>]*\s+)?class\s*=\s*")([^"]*?)(")'
    if re.search(th_replace_pattern, content):
        content = re.sub(th_replace_pattern, r'\1\2 {{ column.attrs.th.class }}\3', content)
    else:
        # If there's no class attribute yet
        content = re.sub(r'(<th[^>]*)', r'\1 class="{{ column.attrs.th.class }}"', content)
    
    # Fix for td elements (table cells)
    td_replace_pattern = r'(<td\s+(?:[^>]*\s+)?class\s*=\s*")([^"]*?)(")'
    if re.search(td_replace_pattern, content):
        content = re.sub(td_replace_pattern, r'\1\2 {{ column.attrs.td.class }}\3', content)
    else:
        # If there's no class attribute yet
        content = re.sub(r'(<td[^>]*)', r'\1 class="{{ column.attrs.td.class }}"', content)
    
    # Write the updated content
    with open(template_path, 'w') as file:
        file.write(content)
    
    print(f"Updated template: {template_path}")
    return True

def verify_js_file():
    """Verify the presence and content of the metadata-toggle.js file."""
    js_file_path = "static/js/metadata-toggle.js"
    
    if not os.path.exists(js_file_path):
        print(f"JavaScript file not found: {js_file_path}")
        print("Looking for it in staticfiles...")
        
        # Try in staticfiles
        js_file_path = "staticfiles/js/metadata-toggle.js"
        if not os.path.exists(js_file_path):
            print(f"JavaScript file not found in staticfiles either.")
            return False
    
    print(f"JavaScript file found: {js_file_path}")
    
    with open(js_file_path, 'r') as file:
        content = file.read()
    
    if 'toggleColumnVisibility' not in content:
        print("WARNING: toggleColumnVisibility function not found in JavaScript file.")
        return False
    
    print("JavaScript file contains the toggleColumnVisibility function.")
    return True

def main():
    """Main function to fix toggle column issues."""
    print("=== OCS Database - Toggle Column Fixer ===")
    
    # Fix table template
    template_fixed = fix_table_template()
    
    # Verify JavaScript
    js_verified = verify_js_file()
    
    print("\n=== Summary ===")
    print(f"Template fixed: {'Yes' if template_fixed else 'No'}")
    print(f"JavaScript verified: {'Yes' if js_verified else 'No'}")
    
    if template_fixed and js_verified:
        print("\nFix completed successfully!")
        print("You need to restart the Django server for changes to take effect.")
        print("Run: python manage.py runserver 0.0.0.0:8090")
    else:
        print("\nFix completed with warnings. Please check the above messages.")

if __name__ == "__main__":
    main() 