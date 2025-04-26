from django.apps import AppConfig

class ViewerConfig(AppConfig):
    name = 'viewer'
    verbose_name = 'Viewer Application'
    
    def ready(self):
        """
        Called when the app is ready.
        Register any signals here.
        """
        # Import modules after the app is fully loaded to avoid circular imports
        from viewer import _import_modules
        _import_modules() 