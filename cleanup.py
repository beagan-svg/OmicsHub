#!/usr/bin/env python
"""
Cleanup script to remove redundant directories after reorganization.
This script will:
1. Check if any important files remain in database_ocs_project
2. Back up any important files
3. Remove the redundant directory
"""

import os
import shutil
import sys
from pathlib import Path

def backup_important_files(directory):
    """Backup any important files from the directory."""
    backup_dir = "backup_files"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Files to ignore (common non-important files)
    ignore = ['.DS_Store', '__pycache__', '*.pyc', '.git']
    
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        if '__pycache__' in root:
            continue
            
        for file in files:
            if file.endswith('.pyc') or file == '.DS_Store':
                continue
                
            source_path = os.path.join(root, file)
            rel_path = os.path.relpath(source_path, directory)
            dest_path = os.path.join(backup_dir, rel_path)
            
            # Create destination directory if it doesn't exist
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Copy the file
            shutil.copy2(source_path, dest_path)
            print(f"Backed up: {source_path} -> {dest_path}")

def remove_directory(directory):
    """Remove the directory and all its contents."""
    if os.path.exists(directory):
        try:
            shutil.rmtree(directory)
            print(f"Successfully removed: {directory}")
            return True
        except Exception as e:
            print(f"Error removing {directory}: {e}")
            return False
    else:
        print(f"Directory not found: {directory}")
        return False

def main():
    """Main execution function."""
    print("Starting cleanup process...")
    
    directory_to_remove = 'database_ocs_project'
    
    if not os.path.exists(directory_to_remove):
        print(f"Directory '{directory_to_remove}' not found. Nothing to clean up.")
        return
    
    # Check if directory is empty
    if not os.listdir(directory_to_remove):
        print(f"Directory '{directory_to_remove}' is empty. Removing...")
        os.rmdir(directory_to_remove)
        print(f"Removed empty directory: {directory_to_remove}")
        return
    
    # Backup files before removal
    print(f"Backing up any important files from '{directory_to_remove}'...")
    backup_important_files(directory_to_remove)
    
    # Remove the directory
    print(f"Removing '{directory_to_remove}'...")
    if remove_directory(directory_to_remove):
        print("Cleanup completed successfully!")
    else:
        print("Cleanup failed. Please check the errors above.")

if __name__ == "__main__":
    main() 