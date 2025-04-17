"""
Pipeline utilities for RNA-seq pipeline management.
This module is kept for backward compatibility and imports from the reorganized modules.
"""

# Import from config module
from .pipeline.config import (
    load_pipeline_config,
    get_reference_name,
    get_chemistry
)

# Import from commands module
from .pipeline.commands import (
    create_bash_script,
    run_bash_script,
    is_ingest_complete,
    determine_workflow,
    create_mtx_alignment_command,
    create_rtx_alignment_command,
    submit_sample_for_alignment
)

# Import from monitoring module
from .pipeline.monitoring import (
    count_running_jobs,
    check_alignment_status,
    stop_alignment_job,
    update_all_running_jobs,
    get_queue_data
)

# For backward compatibility
__all__ = [
    # Config
    'load_pipeline_config',
    'get_reference_name',
    'get_chemistry',
    
    # Commands
    'create_bash_script',
    'run_bash_script',
    'is_ingest_complete',
    'determine_workflow',
    'create_mtx_alignment_command',
    'create_rtx_alignment_command',
    'submit_sample_for_alignment',
    
    # Monitoring
    'count_running_jobs',
    'check_alignment_status',
    'stop_alignment_job',
    'update_all_running_jobs',
    'get_queue_data'
] 