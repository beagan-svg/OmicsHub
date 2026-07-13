"""Serialization helpers for the job-pipeline views.

Single home for turning RunningJob / CompletedJob rows into the plain dicts the
Job Monitor and Pipeline Checkout frontends consume. Kept side-effect free so views just
shape data, and metadata is fetched in one query to avoid N+1 lookups.
"""

from ocs.models import Metadata


def _workflow_for(batch):
    """Display workflow label derived from the vendor batch name."""
    return 'MTX' if batch and 'MTX' in batch else 'RTX'


def _metadata_by_fastq(fastq_names):
    return {m.fastq_name: m for m in Metadata.objects.filter(fastq_name__in=fastq_names)}


def serialize_running_jobs(running_jobs):
    """Serialize RunningJob rows into one dict per active demand.

    Each RunningJob yields an alignment entry and/or a post-QC entry depending on
    which demand ids are set. Output shape matches what the Job Monitor and
    Pipeline Checkout expect.
    """
    jobs = list(running_jobs)
    metadata = _metadata_by_fastq([job.fastq_name for job in jobs])

    serialized = []
    for job in jobs:
        meta = metadata.get(job.fastq_name)
        organism = meta.organism_common_name if meta else 'Unknown'
        batch = meta.batch_name_from_vendor if meta else 'Unknown'
        workflow = _workflow_for(batch)
        time_iso = job.time.isoformat() if job.time else None

        common = {
            'fastq_name': job.fastq_name,
            'time': time_iso,
            'status': 'IN_PROGRESS',
            'start_time': job.time,
            'organism': organism,
            'batch': batch,
            'workflow': workflow,
        }

        if job.alignment_demand_id:
            serialized.append({
                **common,
                'demand_id': job.alignment_demand_id,
                'command': job.alignment_command or '',
                'job_type': 'alignment',
                'attempts': job.alignment_attempts,
            })
        if job.postqc_demand_id:
            serialized.append({
                **common,
                'demand_id': job.postqc_demand_id,
                'command': job.postqc_command or '',
                'job_type': 'post-QC',
                'attempts': job.postqc_attempts,
            })

    return serialized


def serialize_completed_jobs(completed_jobs):
    """Serialize CompletedJob rows (already ordered/sliced by the caller)."""
    jobs = list(completed_jobs)
    metadata = _metadata_by_fastq([job.fastq_name for job in jobs])

    serialized = []
    for job in jobs:
        meta = metadata.get(job.fastq_name)
        serialized.append({
            'fastq_name': job.fastq_name,
            'alignment_demand_id': job.alignment_demand_id,
            'alignment_status': job.alignment_status,
            'alignment_start_time': job.alignment_start_time.isoformat() if job.alignment_start_time else None,
            'alignment_end_time': job.alignment_end_time.isoformat() if job.alignment_end_time else None,
            'alignment_attempts': job.alignment_attempts or 0,
            'alignment_command': job.alignment_command,
            'postqc_demand_id': job.postqc_demand_id,
            'postqc_status': job.postqc_status,
            'postqc_start_time': job.postqc_start_time.isoformat() if job.postqc_start_time else None,
            'postqc_end_time': job.postqc_end_time.isoformat() if job.postqc_end_time else None,
            'postqc_attempts': job.postqc_attempts or 0,
            'postqc_command': job.postqc_command,
            'organism_common_name': meta.organism_common_name if meta else 'Unknown',
            'batch_name_from_vendor': meta.batch_name_from_vendor if meta else 'Unknown',
        })

    return serialized
