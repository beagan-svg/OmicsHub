from django.core.management.base import BaseCommand
import inspect
import os

class Command(BaseCommand):
    help = 'Check which version of MainTable is being used in the web app'

    def handle(self, *args, **options):
        self.stdout.write("Checking MainTable usage in web app...")
        
        # Try to import from the main view that would use MainTable
        try:
            from viewer.views.main import MainListView
            self.stdout.write(f"Successfully imported MainListView from viewer.views.main")
            
            # Check if MainTable is used in the view
            main_list_view_source = inspect.getsource(MainListView)
            self.stdout.write("\nMainListView source code snippet:")
            self.stdout.write("-----------------------------------")
            self.stdout.write("\n".join(main_list_view_source.split("\n")[:20]) + "\n...")
            
            # Check imports in the view file
            view_file_path = inspect.getfile(MainListView)
            self.stdout.write(f"\nView file path: {view_file_path}")
            
            with open(view_file_path, 'r') as file:
                content = file.read()
                import_lines = [line for line in content.split('\n') if 'import' in line]
                self.stdout.write("\nImport statements in the view:")
                for line in import_lines:
                    self.stdout.write(f"  {line}")
                    
            # Check for MainTable references
            maintable_lines = [line for line in content.split('\n') if 'MainTable' in line]
            self.stdout.write("\nMainTable references in the view:")
            for line in maintable_lines:
                self.stdout.write(f"  {line}")
                
            # Check if ImportError is possible
            try:
                from viewer.tables import MainTable as TablesMainTable
                self.stdout.write("\nSuccessfully imported MainTable from viewer.tables")
                self.stdout.write(f"MainTable module: {TablesMainTable.__module__}")
                
                # Check if render methods exist
                render_methods = [method for method in dir(TablesMainTable) if method.startswith('render_') and '_time' in method]
                self.stdout.write("\nTime-related render methods in MainTable:")
                for method in render_methods:
                    self.stdout.write(f"  {method}")
                
            except ImportError as e:
                self.stdout.write(self.style.ERROR(f"\nFailed to import MainTable from viewer.tables: {str(e)}"))
                
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"Failed to import MainListView: {str(e)}"))