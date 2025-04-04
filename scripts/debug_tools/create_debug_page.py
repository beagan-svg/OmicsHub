#!/usr/bin/env python
"""
OCS Database - Debug Page Creator

This script creates a debug page for toggle functionality testing by adding
a new view, template, and URL pattern to the Django application. The debug
page displays all toggle controls and their corresponding table columns in
a simplified layout for easier troubleshooting.

Usage:
    python scripts/debug_tools/create_debug_page.py

Features:
    - Creates a new debug view function
    - Creates a debug template
    - Adds a URL pattern for the debug page
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

from django.template.loader import render_to_string
from django.template import engines

def backup_file(file_path):
    """Create a backup of the specified file."""
    if os.path.exists(file_path):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{file_path}.bak_{timestamp}"
        shutil.copy2(file_path, backup_path)
        print(f"Backup created: {backup_path}")
        return True
    return False

def create_debug_view():
    """Create a debug view function in viewer/views/debug_views.py."""
    views_dir = "viewer/views"
    file_path = f"{views_dir}/debug_views.py"
    
    # Ensure directory exists
    os.makedirs(views_dir, exist_ok=True)
    
    # Backup if file exists
    if os.path.exists(file_path):
        backup_file(file_path)
    
    # Create or update the file
    view_code = '''"""
Debug views for the OCS Database application.
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from viewer.models import UserPreferences
from viewer.tables import MainTable
from viewer.views.main import MainListView

@csrf_exempt
def toggle_debug_view(request):
    """
    Debug view for testing toggle functionality.
    Displays all toggle controls and their corresponding table columns.
    """
    # Get current user preferences
    user_preferences = UserPreferences.get_for_session(request.session)
    
    # Get all toggle fields from UserPreferences model
    toggle_fields = []
    for field in UserPreferences._meta.get_fields():
        if field.name.startswith('toggle_') and field.name != 'toggle_settings_dropdown':
            field_name = field.name[7:]  # Remove 'toggle_' prefix
            toggle_fields.append({
                'name': field_name,
                'enabled': getattr(user_preferences, field.name, True),
                'column_class': f'column-{field_name}',
                'field_name': field.name,
            })
    
    # Get a table instance (for demonstrating columns)
    main_view = MainListView()
    main_view.request = request
    main_view.object_list = main_view.get_queryset()[:10]  # Limit to 10 rows for better performance
    table = main_view.get_table()
    
    context = {
        'toggle_fields': toggle_fields,
        'table': table,
        'user_preferences': user_preferences,
    }
    
    return render(request, 'viewer/debug/toggle_debug.html', context)
'''
    
    with open(file_path, 'w') as file:
        file.write(view_code)
    
    print(f"Created/updated debug view: {file_path}")
    return True

def create_debug_template():
    """Create a debug template for toggle functionality testing."""
    template_dir = "viewer/templates/viewer/debug"
    file_path = f"{template_dir}/toggle_debug.html"
    
    # Ensure directory exists
    os.makedirs(template_dir, exist_ok=True)
    
    # Backup if file exists
    if os.path.exists(file_path):
        backup_file(file_path)
    
    # Create the template
    template_code = '''{% extends "viewer/base.html" %}
{% load static %}
{% load viewer_filters %}

{% block title %}Toggle Debug Page{% endblock %}

{% block extra_css %}
<style>
    .debug-section {
        margin-bottom: 20px;
        padding: 15px;
        border: 1px solid #ddd;
        border-radius: 5px;
    }
    .toggle-section {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
    }
    .toggle-item {
        display: flex;
        align-items: center;
        padding: 5px 10px;
        background-color: #f5f5f5;
        border-radius: 3px;
    }
    .section-title {
        font-weight: bold;
        margin-bottom: 10px;
    }
    .metadata-column {
        padding: 8px;
        border: 1px solid #ddd;
        margin-bottom: 5px;
    }
    .metadata-column.visible {
        background-color: #dff0d8;
    }
    .metadata-column.hidden {
        background-color: #f2dede;
        text-decoration: line-through;
    }
    .column-class {
        font-family: monospace;
        color: #666;
        font-size: 0.9em;
    }
</style>
{% endblock %}

{% block content %}
<div class="container">
    <h1>Toggle Debug Page</h1>
    
    <div class="debug-section">
        <div class="section-title">Toggle Controls</div>
        <div class="toggle-section">
            {% for field in toggle_fields %}
            <div class="toggle-item">
                <input type="checkbox" id="debug_{{ field.field_name }}" 
                       class="toggle-switch" 
                       data-field="{{ field.name }}"
                       {% if field.enabled %}checked{% endif %}>
                <label for="debug_{{ field.field_name }}">{{ field.name }}</label>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <div class="debug-section">
        <div class="section-title">Toggle State in User Preferences</div>
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>Field Name</th>
                    <th>Field Value</th>
                </tr>
            </thead>
            <tbody>
                {% for field in toggle_fields %}
                <tr>
                    <td>{{ field.field_name }}</td>
                    <td>{{ field.enabled }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <div class="debug-section">
        <div class="section-title">Column Classes</div>
        {% for field in toggle_fields %}
        <div class="metadata-column {% if field.enabled %}visible{% else %}hidden{% endif %}">
            <strong>{{ field.name }}</strong> 
            <div class="column-class">.{{ field.column_class }}</div>
        </div>
        {% endfor %}
    </div>
    
    <div class="debug-section">
        <div class="section-title">Example Table (Limited to 10 rows)</div>
        {{ table.as_html }}
    </div>
    
    <div class="debug-section">
        <div class="section-title">Debugging Information</div>
        <ul>
            <li>Number of toggle fields: {{ toggle_fields|length }}</li>
            <li>Table class: {{ table.__class__.__name__ }}</li>
            <li>JavaScript function: <code>toggleColumnVisibility</code></li>
        </ul>
        <div class="section-title">DOM Check</div>
        <pre id="dom-check-result">Click "Run DOM Check" to inspect DOM elements</pre>
        <button id="run-dom-check" class="btn btn-primary">Run DOM Check</button>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
function toggleColumnVisibility(field, enabled) {
    console.log(`Toggle debug: ${field} = ${enabled}`);
    
    // Get all elements with the column class
    const columnClass = `column-${field}`;
    const columnElements = document.querySelectorAll(`.${columnClass}`);
    
    console.log(`Found ${columnElements.length} elements with class ${columnClass}`);
    
    // Toggle the visibility
    columnElements.forEach(element => {
        if (enabled) {
            element.style.display = '';
        } else {
            element.style.display = 'none';
        }
    });
    
    // Update UI in debug view
    document.querySelectorAll('.metadata-column').forEach(el => {
        if (el.querySelector('.column-class').textContent === `.${columnClass}`) {
            if (enabled) {
                el.classList.remove('hidden');
                el.classList.add('visible');
            } else {
                el.classList.remove('visible');
                el.classList.add('hidden');
            }
        }
    });
    
    // Send to server
    fetch('/toggle/update/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            field: field,
            enabled: enabled
        }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('Toggle setting saved');
        } else {
            console.error('Error saving toggle setting', data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

// Handle toggle changes
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.toggle-switch').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const field = this.dataset.field;
            const enabled = this.checked;
            toggleColumnVisibility(field, enabled);
        });
    });
    
    // DOM Check functionality
    document.getElementById('run-dom-check').addEventListener('click', function() {
        const resultElement = document.getElementById('dom-check-result');
        
        // Check table cells for column classes
        let result = '';
        result += 'Table cell classes:\\n';
        
        const tableCells = document.querySelectorAll('td');
        let columnClassCount = 0;
        const columnClassesFound = {};
        
        tableCells.forEach((cell, index) => {
            if (index < 20) { // Limit to first 20 cells for clarity
                const classes = Array.from(cell.classList)
                    .filter(cls => cls.startsWith('column-'));
                
                if (classes.length > 0) {
                    result += `- Cell ${index+1}: ${classes.join(', ')}\\n`;
                    columnClassCount++;
                    
                    classes.forEach(cls => {
                        columnClassesFound[cls] = (columnClassesFound[cls] || 0) + 1;
                    });
                }
            }
        });
        
        result += `\\nTotal cells with column classes: ${columnClassCount}\\n`;
        result += `\\nColumn classes found:\\n`;
        for (const cls in columnClassesFound) {
            result += `- ${cls}: ${columnClassesFound[cls]} occurrences\\n`;
        }
        
        resultElement.textContent = result;
    });
});
</script>
{% endblock %}'''
    
    with open(file_path, 'w') as file:
        file.write(template_code)
    
    print(f"Created debug template: {file_path}")
    return True

def update_urls():
    """Update urls.py to include the debug view."""
    urls_path = "viewer/urls.py"
    
    if not os.path.exists(urls_path):
        print(f"URLs file not found: {urls_path}")
        return False
    
    # Backup the file
    backup_file(urls_path)
    
    with open(urls_path, 'r') as file:
        content = file.read()
    
    # Check if the import is already there
    if "from viewer.views import debug_views" not in content and "from viewer.views.debug_views" not in content:
        # Add import statement
        import_pattern = r"from django.urls import path"
        replacement = "from django.urls import path\nfrom viewer.views import debug_views"
        content = re.sub(import_pattern, replacement, content)
    
    # Check if the URL pattern is already there
    if "debug/toggles/" not in content:
        # Add URL pattern
        urlpatterns_pattern = r'(urlpatterns\s*=\s*\[)'
        replacement = r'\1\n    path("debug/toggles/", debug_views.toggle_debug_view, name="toggle_debug"),'
        content = re.sub(urlpatterns_pattern, replacement, content)
    
    # Write the updated content
    with open(urls_path, 'w') as file:
        file.write(content)
    
    print(f"Updated URLs: {urls_path}")
    return True

def main():
    """Main function to create the debug page."""
    print("=== OCS Database - Debug Page Creator ===")
    
    # Create debug view
    view_created = create_debug_view()
    
    # Create debug template
    template_created = create_debug_template()
    
    # Update URLs
    urls_updated = update_urls()
    
    print("\n=== Summary ===")
    print(f"Debug view created: {'Yes' if view_created else 'No'}")
    print(f"Debug template created: {'Yes' if template_created else 'No'}")
    print(f"URLs updated: {'Yes' if urls_updated else 'No'}")
    
    if view_created and template_created and urls_updated:
        print("\nDebug page created successfully!")
        print("You need to restart the Django server for changes to take effect.")
        print("Access the debug page at: http://localhost:8090/debug/toggles/")
    else:
        print("\nDebug page creation completed with warnings. Please check the above messages.")

if __name__ == "__main__":
    main() 