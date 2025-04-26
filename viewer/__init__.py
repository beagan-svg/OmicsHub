# Root init file for viewer application
default_app_config = 'viewer.core.apps.ViewerConfig'

# The imports will happen after Django has loaded its apps
# to avoid circular dependencies
def _import_modules():
    from . import core
    from . import features
    from . import filters
    from . import utils 