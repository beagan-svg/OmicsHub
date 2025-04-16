"""
Pipeline views for managing alignment and post-alignment jobs.

This module contains views for:
- Pipeline dashboard
- Job monitoring
- Failed jobs management
- Pipeline API endpoints
"""

from typing import Dict, Any, List
from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.views import View
from django.db.models import Prefetch, OuterRef, Subquery, F
from django.core.cache import cache
from concurrent.futures import ThreadPoolExecutor
import os
import yaml
import json
import time
from pathlib import Path
from django.core.paginator import Paginator
from django.utils import timezone
from viewer.models import Main, Metadata, LoadAssociation, Alignment, PostQC, SampleQueue
from viewer.utils.pipeline_utils import (
    load_pipeline_config, 
    count_running_jobs, 
    submit_sample_for_alignment, 
    check_alignment_status,
    stop_alignment_job,
    update_all_running_jobs,
    get_queue_data,
    determine_workflow,
    is_ingest_complete,
    create_mtx_alignment_command,
    create_rtx_alignment_command
)
from django.views.decorators.http import require_http_methods
from django.db import transaction

# Cache timeouts in seconds
PIPELINE_CONFIG_CACHE_TIMEOUT = 3600  # 1 hour
JOB_DATA_CACHE_TIMEOUT = 300         # 5 minutes
JOB_UPDATE_LOCK_TIMEOUT = 60         # 1 minute
JOB_UPDATE_INTERVAL = 600            # 10 minutes

class PipelineDashboardView(TemplateView):
    """View for the main pipeline dashboard."""
    
    template_name = 'viewer/pipeline/dashboard.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Get context data for the pipeline dashboard."""
        context = super().get_context_data(**kwargs)
        
        # Get samples data with efficient querying
        context.update(self._get_samples_data())
        
        # Get pipeline configuration from cache
        context.update(self._get_pipeline_config())
        
        # Get job data from cache
        context.update(self._get_job_data())
        
        # Update job status in background if needed
        self._trigger_background_update()
        
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
        except Exception as e:
            print(f"DEBUG - Pagination Error: {str(e)}")
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
        
        # Get running alignments with efficient querying
        running_alignments = Alignment.objects.filter(
            status_id__in=['SUBMITTED', 'IN_PROGRESS']
        ).select_related('fastq_name').values(
            'fastq_name_id',
            'demand_id',
            'status_id',
            'start_time',
            organism=F('fastq_name__organism_common_name'),
            batch=F('fastq_name__batch_name_from_vendor')
        )
        
        return {
            'job_counts': job_counts,
            'running_alignments': {
                aln['fastq_name_id']: {
                    'demand_id': aln['demand_id'],
                    'status': aln['status_id'],
                    'start_time': aln['start_time'],
                    'organism': aln['organism'],
                    'batch': aln['batch']
                } for aln in running_alignments
            }
        }
    
    def _trigger_background_update(self) -> None:
        """Trigger background job status update if needed."""
        user_id = getattr(self.request.user, 'id', 'anonymous')
        last_update = self.request.session.get('last_job_status_update', 0)
        current_time = timezone.now().timestamp()
        
        if current_time - last_update > JOB_UPDATE_INTERVAL:
            update_cache_key = f'updating_jobs_{user_id}'
            if not cache.get(update_cache_key):
                cache.set(update_cache_key, True, timeout=JOB_UPDATE_LOCK_TIMEOUT)
                with ThreadPoolExecutor() as executor:
                    executor.submit(self._update_jobs_async, user_id)
                self.request.session['last_job_status_update'] = current_time
    
    def _update_jobs_async(self, user_id: str) -> None:
        """Update jobs asynchronously and update cache."""
        try:
            results = update_all_running_jobs()
            job_counts = count_running_jobs()
            cache.set(f'job_counts_{user_id}', job_counts, timeout=JOB_DATA_CACHE_TIMEOUT)
        finally:
            cache.delete(f'updating_jobs_{user_id}')
    
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

class JobMonitorView(TemplateView):
    """View for monitoring running jobs."""
    
    template_name = 'viewer/pipeline/job_monitor.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Get context data for the job monitor."""
        context = super().get_context_data(**kwargs)
        
        # Get user ID for cache key
        user_id = getattr(self.request.user, 'id', 'anonymous')
        
        # Try to get job data from cache first
        context.update(self._get_cached_job_data(user_id))
        
        # Trigger background update if needed
        self._trigger_background_update(user_id)
        
        return context
    
    def _get_cached_job_data(self, user_id: str) -> Dict[str, Any]:
        """Get job data from cache or compute it."""
        cache_key = f'job_monitor_data_{user_id}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Get fresh data if not in cache
        data = self._get_fresh_job_data()
        cache.set(cache_key, data, timeout=JOB_DATA_CACHE_TIMEOUT)
        return data
    
    def _get_fresh_job_data(self) -> Dict[str, Any]:
        """Get fresh job data from database."""
        # Get running and completed jobs
        alignments = Alignment.objects.filter(
            status_id__in=['SUBMITTED', 'IN_PROGRESS']
        ).select_related('fastq_name')
        
        # Get only completed jobs that were submitted through the application (have a demand_id)
        completed_alignments = Alignment.objects.filter(
            status_id__in=['COMPLETED', 'FAILED', 'ABORTED'],
            demand_id__isnull=False  # Only include jobs with a demand_id
        ).exclude(
            demand_id=''  # Exclude empty strings
        ).order_by('-end_time')[:50].select_related('fastq_name')
        
        # Format job data
        running_jobs = self._format_running_jobs(alignments)
        completed_jobs = self._format_completed_jobs(completed_alignments)
        
        # Get job counts
        job_counts = count_running_jobs()
        
        return {
            'running_jobs': running_jobs,
            'completed_jobs': completed_jobs,
            'job_counts': job_counts
        }
    
    def _format_running_jobs(self, alignments: List[Alignment]) -> List[Dict[str, Any]]:
        """Format running jobs for display."""
        return [{
            'fastq_name': alignment.fastq_name_id,
            'demand_id': alignment.demand_id,
            'status': alignment.status_id,
            'start_time': alignment.start_time,
            'organism': alignment.fastq_name.organism_common_name,
            'batch': alignment.fastq_name.batch_name_from_vendor,
            'workflow': 'MTX' if 'MTX' in alignment.fastq_name.batch_name_from_vendor else 'RTX'
        } for alignment in alignments]
    
    def _format_completed_jobs(self, alignments: List[Alignment]) -> List[Dict[str, Any]]:
        """Format completed jobs for display."""
        return [{
            'fastq_name': alignment.fastq_name_id,
            'demand_id': alignment.demand_id,
            'status': alignment.status_id,
            'start_time': alignment.start_time,
            'end_time': alignment.end_time,
            'organism': alignment.fastq_name.organism_common_name,
            'batch': alignment.fastq_name.batch_name_from_vendor,
            'workflow': 'MTX' if 'MTX' in alignment.fastq_name.batch_name_from_vendor else 'RTX',
            'duration': (alignment.end_time - alignment.start_time).total_seconds() // 60 if (alignment.end_time and alignment.start_time) else 0
        } for alignment in alignments]
    
    def _trigger_background_update(self, user_id: str) -> None:
        """Trigger background job status update if needed."""
        last_update = self.request.session.get('last_job_status_update', 0)
        current_time = timezone.now().timestamp()
        
        if current_time - last_update > JOB_UPDATE_INTERVAL:
            update_cache_key = f'updating_jobs_{user_id}'
            if not cache.get(update_cache_key):
                cache.set(update_cache_key, True, timeout=JOB_UPDATE_LOCK_TIMEOUT)
                with ThreadPoolExecutor() as executor:
                    executor.submit(self._update_jobs_async, user_id)
                self.request.session['last_job_status_update'] = current_time
    
    def _update_jobs_async(self, user_id: str) -> None:
        """Update jobs asynchronously and update cache."""
        try:
            update_all_running_jobs()
            fresh_data = self._get_fresh_job_data()
            cache.set(f'job_monitor_data_{user_id}', fresh_data, timeout=JOB_DATA_CACHE_TIMEOUT)
            cache.set(f'job_counts_{user_id}', fresh_data['job_counts'], timeout=JOB_DATA_CACHE_TIMEOUT)
        finally:
            cache.delete(f'updating_jobs_{user_id}')

class FailedJobsView(TemplateView):
    """View for failed jobs that need attention."""
    
    template_name = 'viewer/pipeline/failed_jobs.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Get context data for failed jobs view."""
        context = super().get_context_data(**kwargs)
        
        # Get all failed jobs with retry attempts
        failed_jobs = Alignment.objects.filter(
            status_id='FAILED', 
            retry_count__gte=1
        ).select_related('fastq_name')
        
        # Format for display
        context['failed_jobs'] = [{
            'fastq_name': job.fastq_name_id,
            'demand_id': job.demand_id,
            'start_time': job.start_time,
            'end_time': job.end_time,
            'retry_count': job.retry_count,
            'organism': job.fastq_name.organism_common_name,
            'batch': job.fastq_name.batch_name_from_vendor
        } for job in failed_jobs]
        
        return context

class PipelineApiView:
    """API endpoints for pipeline operations."""
    
    @staticmethod
    def submit_alignment(request) -> JsonResponse:
        """Submit samples for alignment."""
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        try:
            data = json.loads(request.body)
            samples = data.get('samples', [])
            force_submit = data.get('force_submit', False)  # Flag to force submission of samples with incomplete ingest
            
            # Check job capacity
            job_counts = count_running_jobs()
            max_jobs = 100
            if job_counts['total'] >= max_jobs:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Cannot submit more jobs. {job_counts["total"]} jobs already running. Maximum is {max_jobs}.'
                }, status=400)
            
            # Check available slots
            available_slots = max_jobs - job_counts['total']
            
            # Split samples into valid and invalid based on ingest status
            valid_samples = []
            invalid_samples = []
            
            for sample in samples:
                if sample.get('ingest_status') == 'Completed' or force_submit:
                    valid_samples.append(sample)
                else:
                    invalid_samples.append(sample)
            
            # If there are invalid samples and not forcing submission, return warning
            if invalid_samples and not force_submit:
                invalid_names = [s.get('fastq_name', 'Unknown') for s in invalid_samples]
                return JsonResponse({
                    'status': 'warning',
                    'message': f'Some samples have not completed ingest: {", ".join(invalid_names)}',
                    'valid_samples': len(valid_samples),
                    'invalid_samples': invalid_names,
                    'requires_confirmation': True
                })
            
            # Check if we need to limit samples due to capacity
            if len(valid_samples) > available_slots:
                # Truncate the list to available slots
                samples_to_submit = valid_samples[:available_slots]
                overflow_count = len(valid_samples) - available_slots
                overflow_warning = f'Can only submit {available_slots} out of {len(valid_samples)} samples due to capacity limits.'
            else:
                samples_to_submit = valid_samples
                overflow_count = 0
                overflow_warning = None
            
            # Process samples
            results = []
            successful = failed = 0
            submitted_samples = []
            
            for sample in samples_to_submit:
                if sample.get('ingest_status') != 'Completed' and not force_submit:
                    results.append({
                        'fastq_name': sample.get('fastq_name'),
                        'status': 'error',
                        'message': 'Ingest not completed'
                    })
                    failed += 1
                    continue
                
                result = submit_sample_for_alignment(sample)
                results.append(result)
                
                if result.get('status') == 'success':
                    successful += 1
                    submitted_samples.append(sample.get('fastq_name'))
                else:
                    failed += 1
                
                # Add delay between submissions (5 minutes)
                if len(samples_to_submit) > 1 and samples_to_submit.index(sample) < len(samples_to_submit) - 1:
                    time.sleep(300)  # 5 minutes
            
            # Construct response message
            message = f'Processed {len(samples_to_submit)} samples. {successful} successful, {failed} failed.'
            if overflow_warning:
                message = f'{message} {overflow_warning}'
            
            response_status = 'warning' if failed > 0 or overflow_count > 0 else 'success'
            
            return JsonResponse({
                'status': response_status,
                'message': message,
                'results': results,
                'submitted_samples': submitted_samples,
                'successful': successful,
                'failed': failed,
                'overflow_count': overflow_count
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    @staticmethod
    def check_alignment_status(request) -> JsonResponse:
        """Check status of an alignment job."""
        if request.method != 'GET':
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        demand_id = request.GET.get('demand_id', '')
        fastq_name = request.GET.get('fastq_name', '')
        
        if not demand_id and not fastq_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Either demand_id or fastq_name must be provided'
            }, status=400)
        
        try:
            if demand_id:
                return PipelineApiView._check_by_demand_id(demand_id)
            else:
                return PipelineApiView._check_by_fastq_name(fastq_name)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    @staticmethod
    def _check_by_demand_id(demand_id: str) -> JsonResponse:
        """Check alignment status by demand ID."""
        result = check_alignment_status(demand_id)
        
        if result.get('status') == 'success':
            try:
                alignment = Alignment.objects.get(demand_id=demand_id)
                PipelineApiView._update_alignment_status(
                    alignment,
                    result.get('job_status'),
                    update_main=True
                )
            except Alignment.DoesNotExist:
                pass
        
        return JsonResponse(result)
    
    @staticmethod
    def _check_by_fastq_name(fastq_name: str) -> JsonResponse:
        """Check alignment status by FASTQ name."""
        try:
            alignment = Alignment.objects.get(fastq_name=fastq_name)
            
            if not alignment.demand_id:
                return JsonResponse({
                    'status': 'error',
                    'message': f'No demand_id found for {fastq_name}'
                })
            
            result = check_alignment_status(alignment.demand_id)
            
            if result.get('status') == 'success':
                PipelineApiView._update_alignment_status(
                    alignment,
                    result.get('job_status'),
                    update_main=True
                )
            
            return JsonResponse({
                'status': 'success',
                'demand_id': alignment.demand_id,
                'job_status': alignment.status_id,
                'start_time': alignment.start_time,
                'end_time': alignment.end_time
            })
            
        except Alignment.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'No alignment record found for {fastq_name}'
            })
    
    @staticmethod
    def _update_alignment_status(alignment: Alignment, status: str, update_main: bool = False) -> None:
        """Update alignment status and optionally update main table."""
        alignment.status_id = status
        
        if status in ['COMPLETED', 'FAILED', 'ABORTED']:
            alignment.end_time = timezone.now()
        
        alignment.save()
        
        if update_main:
            try:
                main = Main.objects.get(fastq_name=alignment.fastq_name)
                main.alignment_status = {
                    'COMPLETED': 'Completed',
                    'FAILED': 'Failed',
                    'ABORTED': 'Aborted'
                }.get(status, 'In Progress')
                main.save()
            except Main.DoesNotExist:
                pass
    
    @staticmethod
    def stop_alignment(request) -> JsonResponse:
        """Stop a running alignment job."""
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        try:
            data = json.loads(request.body)
            demand_id = data.get('demand_id', '')
            
            if not demand_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'demand_id must be provided'
                }, status=400)
            
            result = stop_alignment_job(demand_id)
            
            if result.get('status') == 'success':
                try:
                    alignment = Alignment.objects.get(demand_id=demand_id)
                    PipelineApiView._update_alignment_status(
                        alignment,
                        'ABORTED',
                        update_main=True
                    )
                except Alignment.DoesNotExist:
                    pass
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    @staticmethod
    def retry_failed_job(request) -> JsonResponse:
        """Retry a failed alignment job."""
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        try:
            data = json.loads(request.body)
            fastq_name = data.get('fastq_name', '')
            
            if not fastq_name:
                return JsonResponse({
                    'status': 'error',
                    'message': 'fastq_name must be provided'
                }, status=400)
            
            try:
                main = Main.objects.select_related('fastq_name').get(fastq_name=fastq_name)
                load_name = LoadAssociation.objects.filter(
                    fastq_name=main.fastq_name
                ).values_list('load_name', flat=True).first() or ''
                
                sample_data = {
                    'fastq_name': fastq_name,
                    'organism_common_name': main.fastq_name.organism_common_name,
                    'batch_name_from_vendor': main.fastq_name.batch_name_from_vendor,
                    'library_prep': main.library_prep_method,
                    'load_name': load_name
                }
                
                result = submit_sample_for_alignment(sample_data)
                return JsonResponse(result)
                
            except Main.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'No record found for {fastq_name}'
                })
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    @staticmethod
    def update_all_jobs(request) -> JsonResponse:
        """Update status of all running jobs."""
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        try:
            results = update_all_running_jobs()
            return JsonResponse({
                'status': 'success',
                'message': f'Updated {len(results)} jobs',
                'results': results
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    @staticmethod
    def get_job_data(request) -> JsonResponse:
        """Get current job data without reloading the page."""
        if request.method != 'GET':
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        try:
            # Get user ID for cache
            user_id = getattr(request.user, 'id', 'anonymous')
            
            # Try to get from cache first
            cache_key = f'job_monitor_data_{user_id}'
            cached_data = cache.get(cache_key)
            
            if cached_data:
                return JsonResponse({
                    'status': 'success',
                    'job_counts': cached_data['job_counts'],
                    'running_jobs': cached_data['running_jobs'],
                    'completed_jobs': cached_data['completed_jobs']
                })
            
            # If not in cache, get fresh data
            view = JobMonitorView()
            fresh_data = view._get_fresh_job_data()
            
            # Cache the fresh data
            cache.set(cache_key, fresh_data, timeout=JOB_DATA_CACHE_TIMEOUT)
            
            return JsonResponse({
                'status': 'success',
                'job_counts': fresh_data['job_counts'],
                'running_jobs': fresh_data['running_jobs'],
                'completed_jobs': fresh_data['completed_jobs']
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    @staticmethod
    def get_queue_data(request) -> JsonResponse:
        """Get data from the alignment and post-QC queues."""
        if request.method != 'GET':
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
        
        try:
            queue_data = get_queue_data()
            
            return JsonResponse({
                'status': 'success',
                'alignment_queue': queue_data['alignment_queue'],
                'postqc_queue': queue_data['postqc_queue']
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_http_methods(["POST"])
def submit_samples(request):
    """API endpoint to submit samples for processing"""
    try:
        data = json.loads(request.body)
        sample_names = data.get('samples', [])
        force_submit = data.get('force_submit', False)
        
        if not sample_names:
            return JsonResponse({'status': 'error', 'message': 'No samples provided'})
        
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
        
        for sample_name in sample_names:
            try:
                # Get sample metadata
                metadata = Metadata.objects.get(fastq_name=sample_name)
                
                # Check if ingest is complete
                if not is_ingest_complete(sample_name) and not force_submit:
                    skipped.append({'fastq_name': sample_name, 'reason': 'Ingest not complete'})
                    continue
                
                # Determine workflow
                workflow = determine_workflow(metadata.batch_name_from_vendor)
                if not workflow:
                    workflow = 'rtx'  # Default to RTX
                
                # Generate command
                if workflow == 'mtx':
                    command = create_mtx_alignment_command({
                        'organism_common_name': metadata.organism_common_name,
                        'load_name': metadata.load_name
                    })
                else:
                    command = create_rtx_alignment_command({
                        'organism_common_name': metadata.organism_common_name,
                        'load_name': metadata.load_name,
                        'library_prep': metadata.library_prep
                    })
                
                # Create or update queue entry
                with transaction.atomic():
                    queue_entry, created = SampleQueue.objects.get_or_create(
                        fastq_name=sample_name,
                        queue_type='alignment',
                        defaults={
                            'workflow': workflow,
                            'command': command,
                            'status': 'pending',
                            'metadata': {
                                'organism': metadata.organism_common_name,
                                'batch': metadata.batch_name_from_vendor,
                                'load_name': metadata.load_name,
                                'library_prep': metadata.library_prep
                            }
                        }
                    )
                    
                    if not created:
                        queue_entry.workflow = workflow
                        queue_entry.command = command
                        queue_entry.status = 'pending'
                        queue_entry.save()
                
                # Submit sample for alignment
                result = submit_sample_for_alignment({
                    'fastq_name': sample_name,
                    'load_name': metadata.load_name,
                    'organism_common_name': metadata.organism_common_name,
                    'batch_name_from_vendor': metadata.batch_name_from_vendor,
                    'library_prep': metadata.library_prep
                })
                
                if result.get('status') == 'success':
                    # Update queue entry with demand ID and start time
                    queue_entry.demand_id = result.get('demand_id')
                    queue_entry.status = 'submitted'
                    queue_entry.start_time = timezone.now()
                    queue_entry.save()
                    
                    submitted.append(sample_name)
                else:
                    skipped.append({
                        'fastq_name': sample_name, 
                        'reason': result.get('message', 'Unknown error')
                    })
                
                # Wait 5 minutes between submissions (unless force submit)
                if not force_submit and sample_name != sample_names[-1]:
                    time.sleep(300)  # 5 minutes in seconds
            
            except Metadata.DoesNotExist:
                skipped.append({'fastq_name': sample_name, 'reason': 'Metadata not found'})
            except Exception as e:
                skipped.append({'fastq_name': sample_name, 'reason': str(e)})
        
        return JsonResponse({
            'status': 'success',
            'submitted': submitted,
            'submitted_count': len(submitted),
            'skipped': skipped,
            'skipped_count': len(skipped)
        })
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}) 