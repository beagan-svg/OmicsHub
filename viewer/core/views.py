from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from .models import QueueJobs
from django.utils import timezone
from django.db import connection

@csrf_exempt
def import_queue(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            queue_entries = data.get('queue', [])
            for entry in queue_entries:
                fastq_name = entry.get('Fastq Name')
                alignment_command = entry.get('Alignment Command', '')
                postqc_command = entry.get('PostQC Command', '')
                status = entry.get('Status', 'pending')  # Default to 'pending' if not provided
                
                # Use current time for queue time
                QueueJobs.objects.update_or_create(
                    fastq_name=fastq_name,
                    defaults={
                        'alignment_command': alignment_command,
                        'postqc_command': postqc_command,
                        'time': timezone.now(),
                        'status': status  # Set the status field
                    }
                )
            return JsonResponse({'status': 'success', 'imported': len(queue_entries)})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

def get_queue_data(request):
    """Get data from the queue_jobs table."""
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
    try:
        print("Starting get_queue_data request...")
        
        # Get all queue entries, ordered by most recent first
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM queue_jobs 
                ORDER BY time DESC
            """)
            columns = [col[0] for col in cursor.description]
            queue_entries = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        print(f"Found {len(queue_entries)} queue entries")
        
        # Create unified queue
        unified_queue = []
        
        for entry in queue_entries:
            fastq_name = entry['fastq_name']
            time_val = entry['time'].isoformat()
            alignment_command = entry['alignment_command']
            postqc_command = entry['postqc_command']
            status = entry['status']

            # If both commands are present and status is pending, split into two rows
            if alignment_command and postqc_command and status.lower() == 'pending':
                unified_queue.append({
                    'fastq_name': fastq_name,
                    'command': alignment_command,
                    'status': 'Ready',
                    'time': time_val
                })
                unified_queue.append({
                    'fastq_name': fastq_name,
                    'command': postqc_command,
                    'status': 'Pending',
                    'time': time_val
                })
            else:
                # Only one command present, or status is not pending
                command = alignment_command or postqc_command or 'N/A'
                unified_queue.append({
                    'fastq_name': fastq_name,
                    'command': command,
                    'status': status,
                    'time': time_val
                })
        
        print(f"Processed queues - Total: {len(unified_queue)}")
        
        return JsonResponse({
            'status': 'success',
            'unified_queue': unified_queue,
            'total_entries': len(unified_queue)
        })
    except Exception as e:
        print(f"Error in get_queue_data: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
def remove_queue_item(request):
    """API endpoint to remove a single item from the queue."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('id')
            
            if not item_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Item ID is required'
                }, status=400)
            
            # Try to get and delete the queue item using fastq_name as the primary key
            try:
                queue_item = QueueJobs.objects.get(fastq_name=item_id)
                fastq_name = queue_item.fastq_name
                queue_item.delete()
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Item {fastq_name} removed successfully',
                    'removed_id': item_id
                })
            except QueueJobs.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Item with ID {item_id} not found'
                }, status=404)
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error removing queue item: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid method'
    }, status=405)

@csrf_exempt
def remove_multiple_queue_items(request):
    """API endpoint to remove multiple items from the queue."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_ids = data.get('ids', [])
            
            if not item_ids:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No item IDs provided'
                }, status=400)
            
            # Get the queue items to delete using fastq_name as the primary key
            queue_items = QueueJobs.objects.filter(fastq_name__in=item_ids)
            count = queue_items.count()
            
            # Delete the queue items
            queue_items.delete()
            
            return JsonResponse({
                'status': 'success',
                'message': f'{count} items removed successfully',
                'removed_count': count
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error removing queue items: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid method'
    }, status=405)

@csrf_exempt
def clear_queue(request):
    """API endpoint to clear the entire queue."""
    if request.method == 'POST':
        try:
            # Delete all queue items
            count = QueueJobs.objects.count()
            QueueJobs.objects.all().delete()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Queue cleared successfully ({count} items removed)',
                'removed_count': count
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error clearing queue: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid method'
    }, status=405)

@csrf_exempt
def process_queue(request):
    """API endpoint to process the next items in the queue."""
    if request.method == 'POST':
        try:
            # In a real implementation, this would trigger processing of queue items
            # For now, we'll just return a success message
            
            return JsonResponse({
                'status': 'success',
                'message': 'Queue processing triggered',
                'processed_count': 0  # Replace with actual count in real implementation
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error processing queue: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid method'
    }, status=405) 