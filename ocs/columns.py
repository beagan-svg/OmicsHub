"""Single source of truth for the samples-browser columns.

Both the server (template SSR) and the client (ColumnManager) read these
defaults, so the initial render matches what the JS settles to (no flash) and
the two can't drift. Used for new users, "Reset", and the "Show All" restore
fallback. Order = the order columns appear in the table.
"""

DEFAULT_COLUMN_VISIBILITY = {
    # Sample information
    'fastq_name': True,
    'study_set': True,
    'load_name': True,
    'batch_name_from_vendor': False,
    'sample_id': False,
    # Sample characteristics
    'organism': False,
    'organism_common_name': True,
    'cell_capture': False,
    'cell_prep_type': False,
    'sequencing_vendor': False,
    # Amplification
    'amplification_name': False,
    'amplification_id': False,
    # Library
    'library_prep_method': True,
    'library_prep_method_id': False,
    'library_prep_name': False,
    'alignment_method': False,
    # Processing status
    'ingest_status': True,
    'alignment_status': True,
    'postqc_status': True,
    # Status FIDs
    'ingest_fid': False,
    'alignment_fid': False,
    'postqc_fid': False,
    # Status times
    'ingest_start_time': False,
    'ingest_end_time': False,
    'alignment_start_time': False,
    'alignment_end_time': False,
    'postqc_start_time': False,
    'postqc_end_time': False,
}


def effective_column_settings(saved):
    """Merge a user's saved visibility over the defaults.

    Saved values win per column; unknown keys are ignored and missing keys fall
    back to the default. Always returns the full, ordered set of known columns.
    """
    saved = saved or {}
    return {
        column: bool(saved.get(column, default))
        for column, default in DEFAULT_COLUMN_VISIBILITY.items()
    }
