from django.views.generic import TemplateView
from django.shortcuts import render
from django.http import JsonResponse
import os
import yaml
import json
from pathlib import Path

class PipelineDashboardView(TemplateView):
    template_name = 'viewer/pipeline/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get pipeline configuration
        config_path = Path(os.path.join('config', 'pipeline_config.yaml'))
        if config_path.exists():
            with open(config_path, 'r') as f:
                try:
                    config = yaml.safe_load(f)
                    context['references'] = config.get('references', {})
                    context['chemistries'] = config.get('chemistries', {})
                except Exception as e:
                    context['config_error'] = str(e)
        else:
            # Use default config for development
            context['references'] = {
                "armadillo": "african-green-monkey_ncbi_vero-who-p1-0_genomefixed_star2.7.1a",
                "human": "human_10x_grch38_genome_star2.7.1a",
                "mouse": "mouse_10x_mm10_genome_star2.7.1a",
                # Add more references as needed
            }
            context['chemistries'] = {
                "10xV3.1D": "SC3Pv3",
                "10xV4": "SC3Pv4",
                # Add more chemistries as needed
            }
        
        # Get running alignments if available
        results_dir = Path('results')
        context['running_alignments'] = {}
        
        if results_dir.exists():
            for file in results_dir.glob('running_submitted_*.json'):
                try:
                    with open(file, 'r') as f:
                        alignments = json.load(f)
                        context['running_alignments'].update(alignments)
                except Exception:
                    pass
        
        return context

class PipelineApiView:
    @staticmethod
    def submit_alignment(request):
        """API endpoint to submit fastq for alignment"""
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                fastq_names = data.get('fastq_names', [])
                workflow = data.get('workflow', '')
                batch_line = data.get('batch_line', '')
                
                # Here you would call your alignment script
                # For now, just return a success response
                return JsonResponse({
                    'status': 'success',
                    'message': f'Submitted {len(fastq_names)} fastq files for {workflow} alignment',
                    'fastq_names': fastq_names,
                    'batch_line': batch_line
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
            fastq_name = request.GET.get('fastq_name', '')
            
            # Here you would check the status using your script
            # For now, just return a sample response
            return JsonResponse({
                'status': 'running',
                'fastq_name': fastq_name,
                'progress': '50%'
            })
        
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request method'
        }, status=405) 