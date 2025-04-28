"""
Compatibility layer for model imports.

This file redirects imports from the old location (viewer.models) to the new location (viewer.core.models).
It maintains backward compatibility with existing code that hasn't been updated yet.
"""

# Re-export all models from core.models
from viewer.core.models import *

# Explicitly re-export common models for better IDE support
from viewer.core.models import (
    Main, 
    Metadata, 
    LoadAssociation, 
    Alignment, 
    PostQC, 
    Ingest,
    QueueJobs
) 