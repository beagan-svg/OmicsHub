"""
Pipeline views for managing alignment and post-alignment jobs.

This module contains views for:
- Pipeline Checkout
- Job monitoring
- Failed jobs management
- Pipeline API endpoints
"""

from typing import Dict, Any, List
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.views import View
from django.db.models import Prefetch, OuterRef, Subquery, F
from django.core.cache import cache
import json
import time
from pathlib import Path
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from ocs.models import Main, Metadata, LoadAssociation, Alignment, PostQC, QueueJobs, FailedJob, RunningJob, CompletedJob
from ocs.pipeline_utils import (
    load_pipeline_config,
    count_running_jobs,
    stop_alignment_job,
    update_all_running_jobs,
    determine_workflow,
    is_ingest_complete,
    create_submission_command,
    move_jobs,
    process_job_status_update,
    create_bash_script,
    run_bash_script,
    TERMINAL_STATUSES,
    MAIN_STATUS_LABELS,
)
from ocs.serializers import serialize_running_jobs
from ocs.jobs import JobMonitorView
from django.views.decorators.http import require_http_methods
from django.db import transaction
import logging

# Cache timeouts in seconds
PIPELINE_CONFIG_CACHE_TIMEOUT = 3600  # 1 hour
JOB_DATA_CACHE_TIMEOUT = 60          # 1 minute (reduced from 5 minutes)
JOB_METADATA_CACHE_TIMEOUT = 300     # 5 minutes for slow-changing metadata

logger = logging.getLogger(__name__)

def invalidate_job_monitor_caches():
    """Invalidate all job monitor caches when job status changes."""
    try:
        # Get all cache keys that match the job monitor pattern
        # Note: This is a simplified approach. In production, you might want
        # to maintain a list of active user cache keys
        
        # Clear the most common cache keys
        cache_patterns = [
            'job_monitor_data_*',
            'job_counts_*'
        ]
        
        # Since Django's cache doesn't support pattern deletion by default,
        # we'll use a different approach: set a cache version
        cache_version = cache.get('job_monitor_cache_version', 0) + 1
        cache.set('job_monitor_cache_version', cache_version, timeout=None)
        
        logger.info(f"Invalidated job monitor caches - new version: {cache_version}")
        
    except Exception:
        logger.exception("Error invalidating job monitor caches")

def get_cache_key_with_version(base_key: str) -> str:
    """Get cache key with version to support cache invalidation."""
    version = cache.get('job_monitor_cache_version', 0)
    return f"{base_key}_v{version}"

class PipelineCheckoutView(LoginRequiredMixin, TemplateView):
    """View for the Pipeline Checkout page."""

    template_name = 'ocs/pipeline/pipeline-checkout.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Get context data for Pipeline Checkout."""
        context = super().get_context_data(**kwargs)
        
        # Get samples data with efficient querying
        context.update(self._get_samples_data())
        
        # Get pipeline configuration from cache
        context.update(self._get_pipeline_config())
        
        # Get job data from cache. Reconciling RunningJob status against the
        # OCS CLI is slow, so it is NOT done in the request path — run
        # `manage.py update_job_status` on a schedule (cron) instead.
        context.update(self._get_job_data())

        return context
    
    def _get_samples_data(self) -> Dict[str, Any]:
        """Get paginated samples data."""
        # Get all samples with related data in a single query
        samples = Main.objects.select_related(
            'fastq_name'
        ).prefetch_related(
            Prefetch(
                'fastq_name__loadassociation_set',
                queryset=LoadAssociation.objects.all(),
                to_attr='load_associations'
            )
        ).all()
        
        # Convert queryset to list of dictionaries efficiently
        samples_data = [
            {
                'fastq': sample.fastq_name.fastq_name,
                'study_set': sample.study_set,
                'load_name': sample.fastq_name.load_associations[0].load_name if hasattr(sample.fastq_name, 'load_associations') and sample.fastq_name.load_associations else '',
                'batch': sample.fastq_name.batch_name_from_vendor,
                'organism': sample.fastq_name.organism_common_name,
                'library_prep': sample.library_prep_method,
                'ingest_status': sample.ingest_status or 'Not Started',
                'alignment_status': sample.alignment_status or 'Not Started',
                'postqc_status': sample.postqc_status or 'Not Started'
            }
            for sample in samples
        ]
        
        # Set up pagination
        per_page = self._get_paginate_by()
        page_number = self.request.GET.get('page', '1')
        
        paginator = Paginator(samples_data, per_page)
        try:
            page_obj = paginator.page(int(page_number))
        except (EmptyPage, PageNotAnInteger, ValueError):
            page_obj = paginator.page(1)
        
        return {
            'page_obj': page_obj,
            'current_per_page': per_page
        }
    
    def _get_pipeline_config(self) -> Dict[str, Any]:
        """Get pipeline configuration from cache or load it."""
        config_cache_key = 'pipeline_config'
        config = cache.get(config_cache_key)
        
        if config is None:
            config = load_pipeline_config()
            cache.set(config_cache_key, config, timeout=PIPELINE_CONFIG_CACHE_TIMEOUT)
        
        return {
            'references': config.get('references', {}),
            'chemistries': config.get('chemistries', {})
        }
    
    def _get_job_data(self) -> Dict[str, Any]:
        """Get job data from cache or compute it."""
        user_id = getattr(self.request.user, 'id', 'anonymous')
        counts_cache_key = f'job_counts_{user_id}'
        job_counts = cache.get(counts_cache_key)
        
        if job_counts is None:
            job_counts = count_running_jobs()
            cache.set(counts_cache_key, job_counts, timeout=JOB_DATA_CACHE_TIMEOUT)

        return {
            'job_counts': job_counts,
            'running_jobs': serialize_running_jobs(RunningJob.objects.all()),
        }
    
    def _get_paginate_by(self) -> int:
        """Get the number of items to display per page."""
        per_page = self.request.GET.get('per_page', '25')
        try:
            per_page = int(per_page)
            if per_page in [10, 25, 50, 100]:
                return per_page
        except (TypeError, ValueError):
            pass
        return 25

class FailedJobsView(LoginRequiredMixin, TemplateView):
    """View for failed jobs that need attention."""
    
    template_name = 'ocs/pipeline/failed_jobs.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Get context data for failed jobs view."""
        context = super().get_context_data(**kwargs)
        
        # Get jobs from failed_jobs table
        failed_jobs_from_table = FailedJob.objects.all().order_by('-time')
        
        # Get all failed alignment jobs that are not in failed_jobs table
        failed_alignments = Alignment.objects.filter(
            status_id__in=['FAILED', 'ABORTED']
        ).exclude(
            fastq_name_id__in=failed_jobs_from_table.values_list('fastq_name', flat=True)
        ).select_related('fastq_name')
        
        # Get all failed post-QC jobs that are not in failed_jobs table
        failed_postqcs = PostQC.objects.filter(
            status_id__in=['FAILED', 'ABORTED']
        ).exclude(
            fastq_name_id__in=failed_jobs_from_table.values_list('fastq_name', flat=True)
        ).select_related('fastq_name')
        
        # Combine all sources of failed jobs
        all_failed_jobs = []
        
        # Process failed_jobs table entries
        for job in failed_jobs_from_table:
            job_type = None
            demand_id = None
            status = "FAILED"  # Default status
            command = None
            
            if job.alignment_demand_id:
                job_type = "alignment"
                demand_id = job.alignment_demand_id
                command = job.alignment_command
                attempts = job.alignment_attempts
            elif job.postqc_demand_id:
                job_type = "post-QC"
                demand_id = job.postqc_demand_id
                command = job.postqc_command
                attempts = job.postqc_attempts
            else:
                # Skip if no demand ID (shouldn't happen, but just in case)
                continue
            
            # Get metadata info if available
            try:
                metadata = Metadata.objects.get(fastq_name=job.fastq_name)
                organism = metadata.organism_common_name
                batch = metadata.batch_name_from_vendor
            except Metadata.DoesNotExist:
                try:
                    main = Main.objects.get(fastq_name=job.fastq_name)
                    organism = main.fastq_name.organism_common_name
                    batch = main.fastq_name.batch_name_from_vendor
                except Main.DoesNotExist:
                    organism = "Unknown"
                    batch = "Unknown"
            
            # Get error details if available
            error_details = ""
            try:
                if job_type == "alignment":
                    alignment = Alignment.objects.get(fastq_name=job.fastq_name)
                    error_details = f"Status: {alignment.status_id}"
                else:
                    postqc = PostQC.objects.get(fastq_name=job.fastq_name)
                    error_details = getattr(postqc, 'status_details', "") or f"Status: {postqc.status_id}"
            except (Alignment.DoesNotExist, PostQC.DoesNotExist):
                pass
            
            all_failed_jobs.append({
                'source': 'failed_jobs_table',
                'fastq_name': job.fastq_name,
                'demand_id': demand_id,
                'job_type': job_type,
                'status': status,
                'command': command,
                'time': job.time,
                'end_time': job.time,
                'attempts': attempts,
                'organism': organism,
                'batch': batch,
                'error_details': error_details,
                'is_retryable': True
            })
        
        # Process failed alignment jobs not in failed_jobs table
        for job in failed_alignments:
            all_failed_jobs.append({
                'source': 'alignment_table',
                'fastq_name': job.fastq_name_id,
                'demand_id': job.demand_id,
                'job_type': 'alignment',
                'status': job.status_id,
                'command': "",
                'start_time': job.start_time,
                'end_time': job.end_time or timezone.now(),
                'time': job.end_time or job.start_time or timezone.now(),
                'attempts': job.retry_count or 1,
                'organism': job.fastq_name.organism_common_name,
                'batch': job.fastq_name.batch_name_from_vendor,
                'error_details': f"Status: {job.status_id}",
                'is_retryable': job.status_id != 'PERMANENTLY_FAILED'
            })
        
        # Process failed post-QC jobs not in failed_jobs table
        for job in failed_postqcs:
            all_failed_jobs.append({
                'source': 'postqc_table',
                'fastq_name': job.fastq_name_id,
                'demand_id': job.demand_id,
                'job_type': 'post-QC',
                'status': job.status_id,
                'command': "",
                'start_time': job.start_time,
                'end_time': job.end_time or timezone.now(),
                'time': job.end_time or job.start_time or timezone.now(),
                'attempts': job.retry_count or 1,
                'organism': job.fastq_name.organism_common_name,
                'batch': job.fastq_name.batch_name_from_vendor,
                'error_details': getattr(job, 'status_details', "") or f"Status: {job.status_id}",
                'is_retryable': job.status_id != 'PERMANENTLY_FAILED'
            })
        
        # Sort by time (most recent first)
        all_failed_jobs.sort(key=lambda x: x.get('end_time') or x.get('time') or timezone.now(), reverse=True)
        
        # Add URL paths for AJAX calls
        context['retry_url'] = reverse('ocs:retry_failed_job')
        context['cancel_url'] = reverse('ocs:cancel_failed_job')
        
        context['failed_jobs'] = all_failed_jobs
        context['failed_job_count'] = len(all_failed_jobs)
        context['job_types'] = ['alignment', 'post-QC']
        context['statuses'] = ['FAILED', 'ABORTED', 'PERMANENTLY_FAILED']
        
        return context

class PipelineApiView:
    """API endpoints for pipeline operations."""
    

    
    @staticmethod
    @login_required
    def check_alignment_status(request) -> JsonResponse:
        """Check status of an alignment job."""
        if request.method != 'GET':
            logger.error('Invalid request method for check_alignment_status: %s', request.method)
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        demand_id = request.GET.get('demand_id', '')
        fastq_name = request.GET.get('fastq_name', '')
        logger.info(f"Checking alignment status: demand_id={demand_id}, fastq_name={fastq_name}")
        if not demand_id and not fastq_name:
            logger.error('Neither demand_id nor fastq_name provided for status check')
            return JsonResponse({
                'status': 'error',
                'message': 'Either demand_id or fastq_name must be provided'
            }, status=400)
        try:
            if demand_id:
                logger.info(f"Checking by demand_id: {demand_id}")
                return PipelineApiView._check_by_demand_id(demand_id)
            else:
                logger.info(f"Checking by fastq_name: {fastq_name}")
                return PipelineApiView._check_by_fastq_name(fastq_name)
        except Exception as e:
            logger.exception(f"Exception in check_alignment_status: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    @staticmethod
    def _check_by_demand_id(demand_id: str) -> JsonResponse:
        logger.info(f"_check_by_demand_id called with demand_id: {demand_id}")
        result = process_job_status_update(demand_id)
        logger.debug(f"Status check result for demand_id {demand_id}: {result}")
        if result.get('status') == 'success':
            try:
                alignment = Alignment.objects.get(demand_id=demand_id)
                PipelineApiView._update_alignment_status(
                    alignment,
                    result.get('job_status'),
                    update_main=True
                )
                logger.info(f"Updated alignment status for demand_id {demand_id} to {result.get('job_status')}")
            except Alignment.DoesNotExist:
                logger.warning(f"No Alignment found for demand_id {demand_id}")
        return JsonResponse(result)
    
    @staticmethod
    def _check_by_fastq_name(fastq_name: str) -> JsonResponse:
        logger.info(f"_check_by_fastq_name called with fastq_name: {fastq_name}")
        try:
            alignment = Alignment.objects.get(fastq_name=fastq_name)
            if not alignment.demand_id:
                logger.error(f"No demand_id found for fastq_name {fastq_name}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'No demand_id found for {fastq_name}'
                })
            result = process_job_status_update(alignment.demand_id)
            logger.debug(f"Status check result for fastq_name {fastq_name}: {result}")
            if result.get('status') == 'success':
                PipelineApiView._update_alignment_status(
                    alignment,
                    result.get('job_status'),
                    update_main=True
                )
                logger.info(f"Updated alignment status for fastq_name {fastq_name} to {result.get('job_status')}")
            return JsonResponse({
                'status': 'success',
                'demand_id': alignment.demand_id,
                'job_status': alignment.status_id,
                'start_time': alignment.start_time,
                'end_time': alignment.end_time
            })
        except Alignment.DoesNotExist:
            logger.error(f"No alignment record found for fastq_name {fastq_name}")
            return JsonResponse({
                'status': 'error',
                'message': f'No alignment record found for {fastq_name}'
            })
        except Exception as e:
            logger.exception(f"Exception in _check_by_fastq_name: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    @staticmethod
    def _update_alignment_status(alignment: Alignment, status: str, update_main: bool = False) -> None:
        """Update alignment status and optionally update main table."""
        alignment.status_id = status

        if status in TERMINAL_STATUSES:
            alignment.end_time = timezone.now()

        alignment.save()

        if update_main:
            try:
                main = Main.objects.get(fastq_name=alignment.fastq_name)
                main.alignment_status = MAIN_STATUS_LABELS.get(status, 'In Progress')
                main.save()
            except Main.DoesNotExist:
                pass
    
    @staticmethod
    @login_required
    def stop_alignment(request, demand_id=None) -> JsonResponse:
        """Stop a running alignment job."""
        if request.method != 'POST':
            logger.error('Invalid request method for stop_alignment: %s', request.method)
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        try:
            # Check if demand_id was provided in URL
            if not demand_id:
                # If not, try to get it from the request body
                data = json.loads(request.body)
                demand_id = data.get('demand_id', '')
                fastq_name = data.get('fastq_name', '')
            else:
                # If demand_id was provided in URL, try to get fastq_name from request body
                try:
                    data = json.loads(request.body)
                    fastq_name = data.get('fastq_name', '')
                except json.JSONDecodeError:
                    fastq_name = ''
            
            logger.info(f"Stopping job: demand_id={demand_id}, fastq_name={fastq_name}")
            
            if not demand_id:
                logger.error('No demand_id provided for stop_alignment')
                return JsonResponse({
                    'status': 'error',
                    'message': 'demand_id must be provided'
                }, status=400)
            
            # Check if we can determine the job type (alignment or post-QC)
            demand_type = 'align'  # Default to align
            if fastq_name:
                try:
                    # Try to find by fastq_name and check which demand_id matches
                    running_job = RunningJob.objects.get(fastq_name=fastq_name)
                    if running_job.alignment_demand_id == demand_id:
                        demand_type = 'align'
                    elif running_job.postqc_demand_id == demand_id:
                        demand_type = 'post-align'
                except RunningJob.DoesNotExist:
                    pass
            else:
                # Try to find by demand_id
                try:
                    running_job = RunningJob.objects.get(alignment_demand_id=demand_id)
                    fastq_name = running_job.fastq_name
                    demand_type = 'align'
                except RunningJob.DoesNotExist:
                    try:
                        running_job = RunningJob.objects.get(postqc_demand_id=demand_id)
                        fastq_name = running_job.fastq_name
                        demand_type = 'post-align'
                    except RunningJob.DoesNotExist:
                        pass
            
            # Stop the job in the OCS service
            logger.info(f"Stopping {demand_type} job with demand_id: {demand_id}")
            result = stop_alignment_job(demand_id)
            logger.info(f"Stop job result: {result}")
            
            if result.get('status') == 'success':
                # Process the job status update
                update_result = process_job_status_update(demand_id)
                
                if update_result.get('status') == 'success':
                    logger.info(f"Successfully processed job status update after stopping job")
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Successfully stopped job with demand_id {demand_id}',
                        'demand_id': demand_id,
                        'demand_type': demand_type,
                        'fastq_name': fastq_name
                    })
                else:
                    logger.warning(f"Job was stopped but status update failed: {update_result.get('message')}")
                    # Return success anyway because the job was stopped
                    return JsonResponse({
                        'status': 'success',
                        'warning': 'Job was stopped but status update failed',
                        'message': f'Successfully stopped job with demand_id {demand_id}',
                        'demand_id': demand_id,
                        'demand_type': demand_type,
                        'fastq_name': fastq_name
                    })
            else:
                logger.error(f"Failed to stop job with demand_id {demand_id}: {result.get('message')}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'Failed to stop job: {result.get("message", "Unknown error")}',
                    'demand_id': demand_id
                }, status=400)
            
        except Exception as e:
            logger.exception(f"Exception in stop_alignment: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    @staticmethod
    @login_required
    def check_job_status(request, demand_id) -> JsonResponse:
        """Check status of a specific job by demand ID."""
        if request.method != 'POST':
            logger.error('Invalid request method for check_job_status: %s', request.method)
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        logger.info(f"Checking job status for demand_id: {demand_id}")
        
        try:
            # Use the comprehensive job status update function
            result = process_job_status_update(demand_id)
            
            if result.get('status') == 'success':
                logger.info(f"Job status update successful: {result}")
                
                # Invalidate cache for all users when job status changes
                # This ensures fresh data is returned on next request
                invalidate_job_monitor_caches()
                
                return JsonResponse({
                    'status': 'success',
                    'job_status': result.get('job_status', 'UNKNOWN'),
                    'demand_type': result.get('demand_type', 'align'),
                    'demand_id': demand_id,
                    'message': result.get('message', 'Job status updated successfully')
                })
            else:
                logger.warning(f"Job status update failed: {result}")
                return JsonResponse({
                    'status': 'error',
                    'message': result.get('message', 'Error updating job status'),
                    'demand_id': demand_id
                }, status=400)
                
        except Exception as e:
            logger.exception(f"Exception in check_job_status: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    @staticmethod
    @login_required
    def retry_failed_job(request) -> JsonResponse:
        """Retry a failed job (alignment or post-QC)."""
        if request.method != 'POST':
            logger.error('Invalid request method for retry_failed_job: %s', request.method)
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        try:
            # Handle both form data and JSON formats
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
                
            fastq_name = data.get('fastq_name', '')
            job_type = data.get('job_type', 'alignment')  # Default to alignment if not specified
            
            logger.info(f"Attempting to retry {job_type} job for {fastq_name}")
            
            if not fastq_name:
                logger.error("No FASTQ name provided for job retry")
                return JsonResponse({
                    'status': 'error',
                    'message': 'fastq_name must be provided'
                }, status=400)
            
            # Get main record to retrieve necessary metadata
            try:
                main = Main.objects.select_related('fastq_name').get(fastq_name=fastq_name)
            except Main.DoesNotExist:
                logger.error(f"No main record found for {fastq_name}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'No record found for {fastq_name}'
                }, status=404)
                
            # Get load name
            load_name = LoadAssociation.objects.filter(
                fastq_name=main.fastq_name
            ).values_list('load_name', flat=True).first() or ''
            
            if not load_name:
                logger.warning(f"No load name found for {fastq_name}, proceeding anyway")
            
            # Prepare sample data for submission
            sample_data = {
                'fastq_name': fastq_name,
                'organism_common_name': main.fastq_name.organism_common_name,
                'batch_name_from_vendor': main.fastq_name.batch_name_from_vendor,
                'library_prep': main.library_prep_method,
                'load_name': load_name
            }
            
            # Check if we need to retry alignment or post-QC
            if job_type.lower() == 'alignment':
                logger.info(f"Submitting alignment job for {fastq_name}")
                
                # Determine workflow from batch name
                workflow = determine_workflow(sample_data.get('batch_name_from_vendor', ''))
                if not workflow:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Could not determine workflow for {fastq_name} with batch name {sample_data.get("batch_name_from_vendor", "")}'
                    }, status=400)
                
                # Generate command. The notification address mirrors the
                # frontend's "$USER@alleninstitute.org" default.
                notification_email = request.user.email or f"{request.user.username}@alleninstitute.org"
                command = create_submission_command(workflow, 'alignment', sample_data, notification_email)

                # Check if command generation failed
                if command is False:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Could not generate command for {fastq_name} - unsupported library prep method: {sample_data.get("library_prep", "N/A")}'
                    }, status=400)
                
                # Execute bash script to submit job
                script_path = create_bash_script(command, f'submit_{fastq_name}.sh')
                output = run_bash_script(script_path)
                
                # Parse result
                try:
                    # In test mode, output is already a JSON string
                    parsed_result = json.loads(output)
                    
                    if 'demand_status' in parsed_result and parsed_result['demand_status'] == 'SUBMITTED':
                        # Success - create result structure
                        result = {
                            'status': 'success',
                            'message': f'Alignment submitted successfully for {fastq_name}',
                            'fastq_name': fastq_name,
                            'demand_id': parsed_result.get('demand_id', 'unknown'),
                            'command': command
                        }
                    else:
                        # Something went wrong
                        result = {
                            'status': 'error',
                            'message': f'Submission failed for {fastq_name}: {output}',
                            'fastq_name': fastq_name
                        }
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse submission output: {output}")
                    # For test mode fallback
                    if "Command logged" in output:
                        result = {
                            'status': 'success',
                            'message': f'Alignment command logged for {fastq_name}',
                            'fastq_name': fastq_name,
                            'demand_id': f'test-demand-{int(time.time())}',
                            'command': command
                        }
                    else:
                        result = {
                            'status': 'error',
                            'message': f'Invalid response from OCS: {output}',
                            'fastq_name': fastq_name
                        }
                
                # If successful, create/update RunningJob record and update other tables
                if result.get('status') == 'success':
                    demand_id = result.get('demand_id', '')
                    
                    with transaction.atomic():
                        # Create or update RunningJob record
                        running_job, created = RunningJob.objects.get_or_create(
                            fastq_name=fastq_name,
                            defaults={
                                'alignment_command': result.get('command', ''),
                                'postqc_command': '',
                                'alignment_attempts': 1,
                                'postqc_attempts': 0,
                                'alignment_demand_id': demand_id,
                                'postqc_demand_id': None
                            }
                        )
                        
                        if not created:
                            # Update existing record
                            running_job.alignment_command = result.get('command', '')
                            running_job.alignment_attempts += 1
                            running_job.alignment_demand_id = demand_id
                            running_job.save()
                        
                        logger.info(f"Updated RunningJob record for {fastq_name}, retry count: {running_job.alignment_attempts}")
                        
                        # Update or create Alignment record
                        alignment, created = Alignment.objects.get_or_create(
                            fastq_name=main.fastq_name,
                            defaults={
                                'status_id': 'SUBMITTED',
                                'start_time': timezone.now(),
                                'end_time': None,
                                'demand_id': demand_id,
                                'retry_count': running_job.alignment_attempts
                            }
                        )
                        
                        if not created:
                            alignment.status_id = 'SUBMITTED'
                            alignment.start_time = timezone.now()
                            alignment.end_time = None
                            alignment.demand_id = demand_id
                            alignment.retry_count = running_job.alignment_attempts
                            alignment.save()
                        
                        # Update main table
                        main.alignment_status = 'Submitted'
                        main.save()
                        
                        # Remove from failed_jobs if present
                        try:
                            failed_job = FailedJob.objects.get(fastq_name=fastq_name)
                            if failed_job.alignment_demand_id:
                                logger.info(f"Removing job from failed_jobs: {fastq_name}")
                                failed_job.delete()
                        except FailedJob.DoesNotExist:
                            pass
                else:
                    # Return error from inline submission logic
                    return JsonResponse(result, status=400)
            else:
                # For now, we'll just return an error since post-QC retry is not implemented
                logger.warning(f"Post-QC job retry not yet implemented for {fastq_name}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Post-QC job retry not yet implemented'
                }, status=400)
            
            logger.info(f"Retry job result: {result}")
            return JsonResponse(result)
                
        except Exception as e:
            logger.exception(f"Exception in retry_failed_job: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    @staticmethod
    @login_required
    def update_all_jobs(request) -> JsonResponse:
        """Update status of all running jobs."""
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        try:
            # Update running jobs
            results = update_all_running_jobs()
            
            # Get fresh job counts
            job_counts = count_running_jobs()
            
            # Invalidate cache for this user after updating jobs
            user_id = getattr(request.user, 'id', 'anonymous')
            cache_keys_to_delete = [
                f'job_monitor_data_{user_id}',
                f'job_counts_{user_id}',
            ]
            
            for cache_key in cache_keys_to_delete:
                cache.delete(cache_key)
                logger.debug(f"Invalidated cache key: {cache_key}")
            
            return JsonResponse({
                'status': 'success',
                'message': f'Updated {len(results)} jobs',
                'results': results,
                'job_counts': job_counts
            })
        except Exception as e:
            logger.exception("Error in update_all_jobs")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    @staticmethod
    @login_required
    def get_job_data(request) -> JsonResponse:
        """Get current job data without reloading the page."""
        if request.method != 'GET':
            logger.error('Invalid request method for get_job_data: %s', request.method)
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        try:
            user_id = getattr(request.user, 'id', 'anonymous')
            logger.info(f"Fetching job data for user_id: {user_id}")
            
            # Check if force refresh is requested (for "Refresh Now" button)
            force_refresh = request.GET.get('force_refresh', 'false').lower() == 'true'
            
            cache_key = f'job_monitor_data_{user_id}'
            cached_data = cache.get(cache_key)
            
            # Only use cached data if force_refresh is not requested
            if cached_data and not force_refresh:
                logger.info(f"Returning cached job data for user_id: {user_id}")
                logger.debug(f"Cached job data: {cached_data}")
                return JsonResponse({
                    'status': 'success',
                    'job_counts': cached_data['job_counts'],
                    'running_jobs': cached_data['running_jobs'],
                    'completed_jobs': cached_data['completed_jobs']
                })
            
            if force_refresh:
                logger.info(f"Force refresh requested for user_id: {user_id}, fetching fresh data from database.")
            else:
                logger.info(f"No cached data found for user_id: {user_id}, fetching fresh data.")
            
            # Get fresh data using the updated method
            view = JobMonitorView()
            fresh_data = view._get_fresh_job_data()
            logger.debug(f"Fresh job data: {fresh_data}")
            
            # Update cache with fresh data
            cache.set(cache_key, fresh_data, timeout=JOB_DATA_CACHE_TIMEOUT)
            
            return JsonResponse({
                'status': 'success',
                'job_counts': fresh_data['job_counts'],
                'running_jobs': fresh_data['running_jobs'],
                'completed_jobs': fresh_data['completed_jobs'],
                'from_cache': False,  # Indicate this is fresh data
                'force_refresh': force_refresh
            })
        except Exception as e:
            logger.exception(f"Exception in get_job_data: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    @staticmethod
    @login_required
    def cancel_failed_job(request) -> JsonResponse:
        """Permanently cancel a failed job by removing it from the failed_jobs table and updating its status."""
        if request.method != 'POST':
            logger.error('Invalid request method for cancel_failed_job: %s', request.method)
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        try:
            # Handle both form data and JSON formats
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
                
            fastq_name = data.get('fastq_name', '')
            job_type = data.get('job_type', 'alignment')  # Default to alignment if not specified
            
            logger.info(f"Attempting to permanently cancel {job_type} job for {fastq_name}")
            
            if not fastq_name:
                logger.error("No FASTQ name provided for job cancellation")
                return JsonResponse({
                    'status': 'error',
                    'message': 'fastq_name must be provided'
                }, status=400)
            
            # First, check if the job is in the failed_jobs table
            try:
                failed_job = FailedJob.objects.get(fastq_name=fastq_name)
                
                # If the job exists, check if it's of the right type
                if job_type.lower() == 'alignment' and not failed_job.alignment_demand_id:
                    logger.warning(f"Failed job for {fastq_name} is not an alignment job")
                elif job_type.lower() != 'alignment' and not failed_job.postqc_demand_id:
                    logger.warning(f"Failed job for {fastq_name} is not a post-QC job")
                
                # Delete the failed job record
                failed_job.delete()
                logger.info(f"Removed job from failed_jobs: {fastq_name}")
                
                # Update the status in the corresponding table
                if job_type.lower() == 'alignment':
                    try:
                        alignment = Alignment.objects.get(fastq_name=fastq_name)
                        alignment.status_id = 'PERMANENTLY_FAILED'
                        alignment.save()
                        
                        # Also update main table
                        try:
                            main = Main.objects.get(fastq_name=fastq_name)
                            main.alignment_status = 'Permanently Failed'
                            main.save()
                        except Main.DoesNotExist:
                            logger.warning(f"No main record found for {fastq_name}")
                    except Alignment.DoesNotExist:
                        logger.warning(f"No alignment record found for {fastq_name}")
                else:
                    try:
                        postqc = PostQC.objects.get(fastq_name=fastq_name)
                        postqc.status_id = 'PERMANENTLY_FAILED'
                        postqc.save()
                        
                        # Also update main table
                        try:
                            main = Main.objects.get(fastq_name=fastq_name)
                            main.postqc_status = 'Permanently Failed'
                            main.save()
                        except Main.DoesNotExist:
                            logger.warning(f"No main record found for {fastq_name}")
                    except PostQC.DoesNotExist:
                        logger.warning(f"No postqc record found for {fastq_name}")
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Job for {fastq_name} has been permanently cancelled'
                })
            except FailedJob.DoesNotExist:
                # If not in failed_jobs, check if it's in the alignment or postqc table
                if job_type.lower() == 'alignment':
                    try:
                        alignment = Alignment.objects.get(fastq_name=fastq_name)
                        if alignment.status_id in ['FAILED', 'ABORTED']:
                            alignment.status_id = 'PERMANENTLY_FAILED'
                            alignment.save()
                            
                            # Also update main table
                            try:
                                main = Main.objects.get(fastq_name=fastq_name)
                                main.alignment_status = 'Permanently Failed'
                                main.save()
                            except Main.DoesNotExist:
                                logger.warning(f"No main record found for {fastq_name}")
                                
                            return JsonResponse({
                                'status': 'success',
                                'message': f'Alignment job for {fastq_name} has been permanently cancelled'
                            })
                        else:
                            logger.warning(f"Alignment job for {fastq_name} is not in a failed state")
                            return JsonResponse({
                                'status': 'error',
                                'message': f'Alignment job for {fastq_name} is not in a failed state'
                            }, status=400)
                    except Alignment.DoesNotExist:
                        logger.error(f"No alignment record found for {fastq_name}")
                        return JsonResponse({
                            'status': 'error',
                            'message': f'No alignment record found for {fastq_name}'
                        }, status=404)
                else:
                    try:
                        postqc = PostQC.objects.get(fastq_name=fastq_name)
                        if postqc.status_id in ['FAILED', 'ABORTED']:
                            postqc.status_id = 'PERMANENTLY_FAILED'
                            postqc.save()
                            
                            # Also update main table
                            try:
                                main = Main.objects.get(fastq_name=fastq_name)
                                main.postqc_status = 'Permanently Failed'
                                main.save()
                            except Main.DoesNotExist:
                                logger.warning(f"No main record found for {fastq_name}")
                                
                            return JsonResponse({
                                'status': 'success',
                                'message': f'Post-QC job for {fastq_name} has been permanently cancelled'
                            })
                        else:
                            logger.warning(f"Post-QC job for {fastq_name} is not in a failed state")
                            return JsonResponse({
                                'status': 'error',
                                'message': f'Post-QC job for {fastq_name} is not in a failed state'
                            }, status=400)
                    except PostQC.DoesNotExist:
                        logger.error(f"No post-QC record found for {fastq_name}")
                        return JsonResponse({
                            'status': 'error',
                            'message': f'No post-QC record found for {fastq_name}'
                        }, status=404)
        except Exception as e:
            logger.exception(f"Exception in cancel_failed_job: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def submit_samples(request):
    """API endpoint to submit samples for processing with pre-generated commands"""
    try:
        data = json.loads(request.body)
        samples = data.get('samples', [])
        force_submit = data.get('force_submit', False)
        
        if not samples:
            return JsonResponse({'status': 'error', 'message': 'No samples provided'})
        
        # Validate that samples have required structure
        for sample in samples:
            if not isinstance(sample, dict) or 'sample_name' not in sample or 'command' not in sample:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Each sample must be an object with sample_name and command fields'
                })
        
        # Check current job count if not forcing submission
        if not force_submit:
            job_counts = count_running_jobs()
            if job_counts['total'] >= 100:
                return JsonResponse({
                    'status': 'error', 
                    'message': f'Too many jobs running ({job_counts["total"]}). Please try again later or use force submit.'
                })
        
        submitted = []
        skipped = []
        
        for sample in samples:
            sample_name = sample.get('sample_name')
            command = sample.get('command')
            
            try:
                # Check if ingest is complete
                if not is_ingest_complete(sample_name) and not force_submit:
                    skipped.append({'fastq_name': sample_name, 'reason': 'Ingest not complete'})
                    continue
                
                # Validate that command is provided
                if not command:
                    skipped.append({
                        'fastq_name': sample_name,
                        'reason': 'No submission command provided'
                    })
                    continue
                
                # Execute bash script to submit job
                script_path = create_bash_script(command, f'submit_{sample_name}.sh')
                output = run_bash_script(script_path)
                
                # Parse result
                try:
                    # In test mode, output is already a JSON string
                    result = json.loads(output)
                    
                    if 'demand_status' in result and result['demand_status'] == 'SUBMITTED':
                        # Success - create result structure
                        result = {
                            'status': 'success',
                            'message': f'Alignment submitted successfully for {sample_name}',
                            'fastq_name': sample_name,
                            'demand_id': result.get('demand_id', 'unknown'),
                            'command': command
                        }
                    else:
                        # Something went wrong
                        result = {
                            'status': 'error',
                            'message': f'Submission failed for {sample_name}: {output}',
                            'fastq_name': sample_name
                        }
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse submission output: {output}")
                    # For test mode fallback
                    if "Command logged" in output:
                        result = {
                            'status': 'success',
                            'message': f'Alignment command logged for {sample_name}',
                            'fastq_name': sample_name,
                            'demand_id': f'test-demand-{int(time.time())}',
                            'command': command
                        }
                    else:
                        result = {
                            'status': 'error',
                            'message': f'Invalid response from OCS: {output}',
                            'fastq_name': sample_name
                        }
                
                if result.get('status') == 'success':
                    demand_id = result.get('demand_id', '')
                    
                    with transaction.atomic():
                        # Create or update RunningJob record
                        running_job, created = RunningJob.objects.get_or_create(
                            fastq_name=sample_name,
                            defaults={
                                'alignment_command': command,
                                'postqc_command': '',
                                'alignment_attempts': 1,
                                'postqc_attempts': 0,
                                'alignment_demand_id': demand_id,
                                'postqc_demand_id': None
                            }
                        )
                        
                        if not created:
                            # Update existing record
                            running_job.alignment_command = command
                            running_job.alignment_attempts += 1
                            running_job.alignment_demand_id = demand_id
                            running_job.save()
                        
                        # Create or update queue entry
                        queue_entry, queue_created = QueueJobs.objects.get_or_create(
                            fastq_name=sample_name,
                            defaults={
                                'alignment_command': command,
                                'status': 'Running',
                                'time': timezone.now(),
                                'user': request.user
                            }
                        )

                        if not queue_created:
                            queue_entry.alignment_command = command
                            queue_entry.status = 'Running'
                            queue_entry.time = timezone.now()
                            queue_entry.user = request.user
                            queue_entry.save()
                        
                        # Update or create Alignment record
                        try:
                            main = Main.objects.get(fastq_name=sample_name)
                            alignment, alignment_created = Alignment.objects.get_or_create(
                                fastq_name=main.fastq_name,
                                defaults={
                                    'status_id': 'SUBMITTED',
                                    'start_time': timezone.now(),
                                    'demand_id': demand_id,
                                    'retry_count': running_job.alignment_attempts
                                }
                            )
                            
                            if not alignment_created:
                                alignment.status_id = 'SUBMITTED'
                                alignment.start_time = timezone.now()
                                alignment.end_time = None
                                alignment.demand_id = demand_id
                                alignment.retry_count = running_job.alignment_attempts
                                alignment.save()
                            
                            # Update main table
                            main.alignment_status = 'Submitted'
                            main.save()
                            
                        except Main.DoesNotExist:
                            logger.warning(f"No main record found for {sample_name}")
                    
                    submitted.append(sample_name)
                else:
                    skipped.append({
                        'fastq_name': sample_name,
                        'reason': result.get('message', 'Unknown error')
                    })

            except Exception as e:
                logger.exception("Error submitting sample %s", sample_name)
                skipped.append({'fastq_name': sample_name, 'reason': str(e)})
        
        return JsonResponse({
            'status': 'success',
            'submitted': submitted,
            'submitted_count': len(submitted),
            'skipped': skipped,
            'skipped_count': len(skipped)
        })

    except Exception as e:
        logger.exception("Unexpected error in submit_samples")
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
@require_http_methods(["GET"])
def pipeline_config(request):
    """Serve the pipeline configuration to the frontend submission modal."""
    config = load_pipeline_config()
    if not config:
        return JsonResponse({'error': 'Failed to load pipeline configuration'}, status=500)
    return JsonResponse(config)
