import os
import shutil
from pathlib import Path

def create_directories():
    """Create new directory structure."""
    dirs = [
        'config/settings',
        'scripts/shell',
        'scripts/management',
        'data/csv',
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {d}")

def move_files():
    """Move files to their new locations."""
    moves = [
        ('database_ocs_project/settings/*', 'config/settings/'),
        ('database_ocs_project/*.sh', 'scripts/shell/'),
        ('database_ocs_project/*.csv', 'data/csv/'),
        ('database_ocs_project/urls.py', 'config/'),
        ('database_ocs_project/wsgi.py', 'config/'),
        ('database_ocs_project/asgi.py', 'config/'),
        ('database_ocs/management/', 'scripts/management/'),
    ]
    
    for src, dst in moves:
        if '*' in src:
            # Handle glob patterns
            import glob
            for file in glob.glob(src):
                if os.path.exists(file):
                    shutil.move(file, dst)
                    print(f"Moved {file} to {dst}")
        else:
            if os.path.exists(src):
                shutil.move(src, dst)
                print(f"Moved {src} to {dst}")

def update_imports():
    """Update import paths in Python files."""
    files_to_update = {
        'manage.py': {
            'from': "database_ocs_project.settings.development",
            'to': "config.settings.development"
        },
        'config/wsgi.py': {
            'from': "database_ocs_project.settings",
            'to': "config.settings"
        },
        'config/asgi.py': {
            'from': "database_ocs_project.settings",
            'to': "config.settings"
        }
    }
    
    for file, changes in files_to_update.items():
        if os.path.exists(file):
            with open(file, 'r') as f:
                content = f.read()
            
            content = content.replace(changes['from'], changes['to'])
            
            with open(file, 'w') as f:
                f.write(content)
            print(f"Updated imports in {file}")

def main():
    """Main execution function."""
    print("Starting project reorganization...")
    
    # Create new directory structure
    create_directories()
    
    # Move files to new locations
    move_files()
    
    # Update import paths
    update_imports()
    
    # Clean up empty directories
    if os.path.exists('database_ocs_project') and not os.listdir('database_ocs_project'):
        os.rmdir('database_ocs_project')
        print("Removed empty database_ocs_project directory")
    
    if os.path.exists('database_ocs') and not os.listdir('database_ocs'):
        os.rmdir('database_ocs')
        print("Removed empty database_ocs directory")
    
    print("\nProject reorganization complete!")
    print("\nPlease verify the changes and test the application.")
    print("You may need to update additional import statements in your application code.")

if __name__ == "__main__":
    main() 