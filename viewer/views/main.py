from django.shortcuts import render
from django_tables2 import SingleTableView
from django_tables2.export.views import ExportMixin
from django.views.generic import ListView
from django.http import HttpResponse
from django.db.models import Prefetch, Q
import subprocess
from viewer.models import Main, Metadata, LoadAssociation
from viewer.tables import MainTable
from viewer.filters import MainFilter
from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin

class MainListView(SingleTableMixin, FilterView):
    model = Main
    table_class = MainTable
    template_name = 'viewer/main_list.html'
    filterset_class = MainFilter
    paginate_by = 25

    def get_queryset(self):
        """
        Optimize the queryset with select_related and prefetch_related
        """
        queryset = Main.objects.select_related(
            'fastq_name'
        ).prefetch_related(
            Prefetch(
                'fastq_name__loadassociation_set',
                queryset=LoadAssociation.objects.select_related('fastq_name')
            )
        ).order_by('fastq_name__fastq_name')  # Order by fastq_name for consistent pagination
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add filter data to context"""
        context = super().get_context_data(**kwargs)
        
        # Add filter options to context
        context['study_sets'] = sorted(Main.objects.filter(
            study_set__isnull=False
        ).exclude(study_set='').values_list('study_set', flat=True).distinct())
        
        context['organisms'] = sorted(Main.objects.filter(
            organism__isnull=False
        ).exclude(organism='').values_list('organism', flat=True).distinct())
        
        context['library_prep_methods'] = sorted(Main.objects.filter(
            library_prep_method__isnull=False
        ).exclude(library_prep_method='').values_list('library_prep_method', flat=True).distinct())
        
        # Add alignment, postqc, and ingest status options
        context['alignment_status_options'] = sorted(Main.objects.filter(
            alignment_status__isnull=False
        ).exclude(alignment_status='').values_list('alignment_status', flat=True).distinct())
        
        context['postqc_status_options'] = sorted(Main.objects.filter(
            postqc_status__isnull=False
        ).exclude(postqc_status='').values_list('postqc_status', flat=True).distinct())
        
        context['ingest_status_options'] = sorted(Main.objects.filter(
            ingest_status__isnull=False
        ).exclude(ingest_status='').values_list('ingest_status', flat=True).distinct())
        
        # Add search term to context
        context['search_term'] = self.request.GET.get('search', '')
        
        # Add request parameters to context for form persistence
        context['current_filters'] = dict(self.request.GET.items())
        
        return context

    def post(self, request, *args, **kwargs):
        if 'submit_batch' in request.POST:
            # Get the filtered queryset
            queryset = self.get_queryset()
            
            # Extract unique values from related Metadata model
            load_names = LoadAssociation.objects.filter(
                fastq_name__in=queryset.values_list('fastq_name', flat=True)
            ).values_list('load_name', flat=True).distinct()
            
            organisms = Metadata.objects.filter(
                fastq_name__in=queryset.values_list('fastq_name', flat=True)
            ).values_list('organism_name', flat=True).distinct()
            
            library_prep_methods = Metadata.objects.filter(
                fastq_name__in=queryset.values_list('fastq_name', flat=True)
            ).values_list('library_prep_method_name', flat=True).distinct()
            
            # Create the command
            cmd = ['./process_batch.sh']
            cmd.extend(load_names)
            cmd.extend(organisms)
            cmd.extend(library_prep_methods)
            
            # Execute the command
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    return HttpResponse("Batch processing started successfully")
                else:
                    return HttpResponse(f"Error: {result.stderr}")
            except Exception as e:
                return HttpResponse(f"Error: {str(e)}")
        
        return super().get(request, *args, **kwargs) 