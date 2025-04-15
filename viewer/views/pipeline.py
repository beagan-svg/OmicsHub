from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.views import View
from django.db.models import Prefetch, OuterRef, Subquery, F
from django.core.cache import cache
import os
import yaml
import json
from pathlib import Path
from django.core.paginator import Paginator
from django.utils import timezone
from viewer.models import Main, Metadata, LoadAssociation, Alignment, PostQC
from viewer.utils.pipeline_utils import (
    load_pipeline_config, 
    count_running_jobs, 
    submit_sample_for_alignment, 
    check_alignment_status as check_job_status,
    stop_alignment_job,
    update_all_running_jobs
)

class PipelineDashboardView(TemplateView):
    template_name = 'viewer/pipeline/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
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
        samples_data = []
        for sample in samples:
            # Get load name from prefetched data
            load_name = ''
            if hasattr(sample.fastq_name, 'load_associations') and sample.fastq_name.load_associations:
                load_name = sample.fastq_name.load_associations[0].load_name
            
            samples_data.append({
                'fastq': sample.fastq_name.fastq_name,
                'study_set': sample.study_set,
                'load_name': load_name,
                'batch': sample.fastq_name.batch_name_from_vendor,
                'organism': sample.fastq_name.organism_common_name,
                'library_prep': sample.library_prep_method,
                'ingest_status': sample.ingest_status or 'Not Started',
                'alignment_status': sample.alignment_status or 'Not Started',
                'postqc_status': sample.postqc_status or 'Not Started'
            })
        
        # Get pagination parameters from request
        per_page = self.get_paginate_by()
        page_number = self.request.GET.get('page', '1')
        
        # Set up pagination with actual samples
        paginator = Paginator(samples_data, per_page)
        try:
            page_number = int(page_number)
            page_obj = paginator.page(page_number)
        except Exception as e:
            print(f"DEBUG - Pagination Error: {str(e)}")
            page_obj = paginator.page(1)
        
        context['page_obj'] = page_obj
        context['current_per_page'] = per_page
        
        # Cache pipeline configuration
        cache_key = 'pipeline_config'
        config = cache.get(cache_key)
        if config is None:
            config = load_pipeline_config()
            cache.set(cache_key, config, timeout=3600)  # Cache for 1 hour
        context['references'] = config.get('references', {})
        context['chemistries'] = config.get('chemistries', {})
        
        # Get job counts from cache or compute
        cache_key = f'job_counts_{self.request.user.id}'
        job_counts = cache.get(cache_key)
        if job_counts is None:
            job_counts = count_running_jobs()
            cache.set(cache_key, job_counts, timeout=300)  # Cache for 5 minutes
        context['job_counts'] = job_counts
        
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
        
        # Format for display using dict comprehension
        context['running_alignments'] = {
            aln['fastq_name_id']: {
                'demand_id': aln['demand_id'],
                'status': aln['status_id'],
                'start_time': aln['start_time'],
                'organism': aln['organism'],
                'batch': aln['batch']
            } for aln in running_alignments
        }
        
        # Check if we need to update job status (async)
        last_update = self.request.session.get('last_job_status_update', 0)
        current_time = timezone.now().timestamp()
        
        if current_time - last_update > 600:  # 10 minutes in seconds
            from django.core.cache import cache
            cache_key = f'updating_jobs_{self.request.user.id}'
            if not cache.get(cache_key):
                # Set a lock to prevent multiple updates
                cache.set(cache_key, True, timeout=60)
                # Update job status asynchronously
                from django.core.cache import cache
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor() as executor:
                    executor.submit(self._update_jobs_async, self.request.user.id)
                self.request.session['last_job_status_update'] = current_time
        
        return context
    
    def _update_jobs_async(self, user_id):
        """Update jobs asynchronously and update cache"""
        try:
            results = update_all_running_jobs()
            # Update job counts in cache
            job_counts = count_running_jobs()
            cache.set(f'job_counts_{user_id}', job_counts, timeout=300)
        finally:
            # Release the lock
            cache.delete(f'updating_jobs_{user_id}')
    
    def get_paginate_by(self):
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
    """View for monitoring running jobs"""
    template_name = 'viewer/pipeline/job_monitor.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Update all running jobs first to ensure database is in sync
        update_all_running_jobs()
        
        # Get all running alignment jobs
        alignments = Alignment.objects.filter(
            status_id__in=['SUBMITTED', 'IN_PROGRESS']
        ).select_related('fastq_name')
        
        # Get all completed/failed alignment jobs (last 50)
        completed_alignments = Alignment.objects.filter(
            status_id__in=['COMPLETED', 'FAILED', 'ABORTED']
        ).order_by('-end_time')[:50].select_related('fastq_name')
        
        # Format for display
        context['running_jobs'] = [{
            'fastq_name': alignment.fastq_name_id,
            'demand_id': alignment.demand_id,
            'status': alignment.status_id,
            'start_time': alignment.start_time,
            'organism': alignment.fastq_name.organism_common_name,
            'batch': alignment.fastq_name.batch_name_from_vendor,
            'workflow': 'MTX' if 'MTX' in alignment.fastq_name.batch_name_from_vendor else 'RTX'
        } for alignment in alignments]
        
        context['completed_jobs'] = [{
            'fastq_name': alignment.fastq_name_id,
            'demand_id': alignment.demand_id,
            'status': alignment.status_id,
            'start_time': alignment.start_time,
            'end_time': alignment.end_time,
            'organism': alignment.fastq_name.organism_common_name,
            'batch': alignment.fastq_name.batch_name_from_vendor,
            'workflow': 'MTX' if 'MTX' in alignment.fastq_name.batch_name_from_vendor else 'RTX',
            'duration': (alignment.end_time - alignment.start_time).total_seconds() // 60 if (alignment.end_time and alignment.start_time) else 0  # in minutes
        } for alignment in completed_alignments]
        
        # Get fresh job counts
        job_counts = count_running_jobs()
        context['job_counts'] = job_counts
        
        return context

class FailedJobsView(TemplateView):
    """View for failed jobs that need attention"""
    template_name = 'viewer/pipeline/failed_jobs.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all failed jobs
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
    @staticmethod
    def submit_alignment(request):
        """API endpoint to submit fastq for alignment"""
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                samples = data.get('samples', [])
                
                # Check if we have capacity to submit more jobs
                job_counts = count_running_jobs()
                
                if job_counts['total'] >= 100:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Cannot submit more jobs. {job_counts["total"]} jobs already running. Maximum is 100.'
                    }, status=400)
                
                # Check how many new jobs we can submit
                available_slots = 100 - job_counts['total']
                
                if len(samples) > available_slots:
                    return JsonResponse({
                        'status': 'warning',
                        'message': f'Can only submit {available_slots} out of {len(samples)} samples due to capacity limits.'
                    }, status=200)
                
                # Process samples
                results = []
                successful = 0
                failed = 0
                
                for sample in samples:
                    # Check if ingest is complete
                    if sample.get('ingest_status') != 'Completed':
                        results.append({
                            'fastq_name': sample.get('fastq_name'),
                            'status': 'error',
                            'message': 'Ingest not completed'
                        })
                        failed += 1
                        continue
                    
                    # Submit for alignment
                    result = submit_sample_for_alignment(sample)
                    
                    if result.get('status') == 'success':
                        successful += 1
                    else:
                        failed += 1
                        
                    results.append(result)
                    
                    # Add delay between submissions
                    if len(samples) > 1:
                        import time
                        time.sleep(300)  # 5 minutes
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Processed {len(samples)} samples. {successful} successful, {failed} failed.',
                    'results': results
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
        
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request method'
        }, status=405)
    
    @staticmethod
    def check_alignment_status(request):
        """API endpoint to check alignment status"""
        if request.method == 'GET':
            demand_id = request.GET.get('demand_id', '')
            fastq_name = request.GET.get('fastq_name', '')
            
            if not demand_id and not fastq_name:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Either demand_id or fastq_name must be provided'
                }, status=400)
            
            if demand_id:
                # Check status by demand_id
                result = check_job_status(demand_id)
                
                if result.get('status') == 'success':
                    # Also update the database with this status
                    try:
                        alignment = Alignment.objects.get(demand_id=demand_id)
                        alignment.status_id = result.get('job_status')
                        
                        if result.get('job_status') in ['COMPLETED', 'FAILED', 'ABORTED']:
                            alignment.end_time = timezone.now()
                            
                        alignment.save()
                        
                        # Also update the main table
                        main = Main.objects.get(fastq_name=alignment.fastq_name)
                        
                        if result.get('job_status') == 'COMPLETED':
                            main.alignment_status = 'Completed'
                        elif result.get('job_status') == 'FAILED':
                            main.alignment_status = 'Failed'
                        elif result.get('job_status') == 'ABORTED':
                            main.alignment_status = 'Aborted'
                        else:
                            main.alignment_status = 'In Progress'
                            
                        main.save()
                    except Alignment.DoesNotExist:
                        pass  # No alignment record found, that's okay
                    
                return JsonResponse(result)
                
            else:
                # Check status by fastq_name
                try:
                    alignment = Alignment.objects.get(fastq_name=fastq_name)
                    
                    if alignment.demand_id:
                        # Check status from the service
                        result = check_job_status(alignment.demand_id)
                        
                        if result.get('status') == 'success':
                            # Update the database
                            alignment.status_id = result.get('job_status')
                            
                            if result.get('job_status') in ['COMPLETED', 'FAILED', 'ABORTED']:
                                alignment.end_time = timezone.now()
                                
                            alignment.save()
                            
                            # Also update the main table
                            main = Main.objects.get(fastq_name=fastq_name)
                            
                            if result.get('job_status') == 'COMPLETED':
                                main.alignment_status = 'Completed'
                            elif result.get('job_status') == 'FAILED':
                                main.alignment_status = 'Failed'
                            elif result.get('job_status') == 'ABORTED':
                                main.alignment_status = 'Aborted'
                            else:
                                main.alignment_status = 'In Progress'
                                
                            main.save()
                        
                        return JsonResponse({
                            'status': 'success',
                            'demand_id': alignment.demand_id,
                            'job_status': alignment.status_id,
                            'start_time': alignment.start_time,
                            'end_time': alignment.end_time
                        })
                    else:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'No demand_id found for {fastq_name}'
                        })
                        
                except Alignment.DoesNotExist:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'No alignment record found for {fastq_name}'
                    })
        
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request method'
        }, status=405)
    
    @staticmethod
    def stop_alignment(request):
        """API endpoint to stop a running alignment job"""
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                demand_id = data.get('demand_id', '')
                
                if not demand_id:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'demand_id must be provided'
                    }, status=400)
                
                # Try to stop the job
                result = stop_alignment_job(demand_id)
                
                if result.get('status') == 'success':
                    # Update the database
                    try:
                        alignment = Alignment.objects.get(demand_id=demand_id)
                        alignment.status_id = 'ABORTED'
                        alignment.end_time = timezone.now()
                        alignment.save()
                        
                        # Update main table
                        main = Main.objects.get(fastq_name=alignment.fastq_name)
                        main.alignment_status = 'Aborted'
                        main.save()
                    except Alignment.DoesNotExist:
                        pass  # No alignment record found, that's okay
                
                return JsonResponse(result)
                
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
        
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request method'
        }, status=405)
    
    @staticmethod
    def retry_failed_job(request):
        """API endpoint to retry a failed alignment job"""
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                fastq_name = data.get('fastq_name', '')
                
                if not fastq_name:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'fastq_name must be provided'
                    }, status=400)
                
                try:
                    # Get the necessary sample data
                    main = Main.objects.select_related('fastq_name').get(fastq_name=fastq_name)
                    
                    # Get load name from related LoadAssociation table
                    load_name = ''
                    load_assoc = LoadAssociation.objects.filter(fastq_name=main.fastq_name).first()
                    if load_assoc:
                        load_name = load_assoc.load_name
                    
                    sample_data = {
                        'fastq_name': fastq_name,
                        'organism_common_name': main.fastq_name.organism_common_name,
                        'batch_name_from_vendor': main.fastq_name.batch_name_from_vendor,
                        'library_prep': main.library_prep_method,
                        'load_name': load_name
                    }
                    
                    # Submit for alignment
                    result = submit_sample_for_alignment(sample_data)
                    
                    return JsonResponse(result)
                    
                except Main.DoesNotExist:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'No record found for {fastq_name}'
                    })
                    
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
        
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request method'
        }, status=405)
    
    @staticmethod
    def update_all_jobs(request):
        """API endpoint to update status of all running jobs"""
        if request.method == 'POST':
            try:
                results = update_all_running_jobs()
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Updated {len(results)} jobs',
                    'results': results
                })
                
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
        
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request method'
        }, status=405) 