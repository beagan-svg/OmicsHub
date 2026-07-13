import functools
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone

from .models import QueueControl, QueueJobs, RunningJob
from ocs.pipeline_utils import create_bash_script, run_bash_script, count_running_jobs

logger = logging.getLogger(__name__)

# Maximum number of jobs allowed to run concurrently in OCS.
MAX_RUNNING_JOBS = 100


def superuser_required(view_func):
    """Allow only authenticated superusers; return 403 JSON otherwise.

    Used to gate the queue master controls (process / pause / stop / reset /
    clear / reorder). Permissions are enforced here in the backend, not only by
    hiding buttons in the UI.
    """
    @functools.wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            return JsonResponse(
                {'status': 'error', 'message': 'Superuser privileges required'},
                status=403,
            )
        return view_func(request, *args, **kwargs)
    return _wrapped


# ---------------------------------------------------------------------------
# Backend queue processor
#
# Job submission is owned by the backend, not the browser. The
# ``process_queue`` management command (cron) calls process_next_queue_job(),
# and a superuser can trigger it manually via the process_queue endpoint.
# ---------------------------------------------------------------------------

def _parse_demand_id(output):
    """Extract a demand_id from OCS command output, or None on failure.

    Mirrors OCS behaviour: a JSON response with ``demand_status == 'SUBMITTED'``,
    or the test-mode ``Command logged`` / ``submitted`` fallback.
    """
    try:
        result = json.loads(output)
    except json.JSONDecodeError:
        if "Command logged" in output or "submitted" in output.lower():
            return f'test-demand-{int(timezone.now().timestamp())}'
        return None

    if result.get('demand_status') != 'SUBMITTED':
        return None

    demand_execution = result.get('demand_execution') or {}
    return (
        demand_execution.get('demand_id')
        or result.get('demand_id')
        or f'unknown-{int(timezone.now().timestamp())}'
    )


def _finalize_success(queue_job, running_job, demand_type, demand_id):
    """Record a successful submission: store the demand_id on the RunningJob and
    clear the executed command from the queue row (deleting it when empty)."""
    with transaction.atomic():
        running_job.refresh_from_db()
        if demand_type == 'alignment':
            running_job.alignment_demand_id = demand_id
        else:
            running_job.postqc_demand_id = demand_id
        running_job.save()

        queue_job.refresh_from_db()
        if demand_type == 'alignment':
            queue_job.alignment_command = None
        else:
            queue_job.postqc_command = None

        if not queue_job.alignment_command and not queue_job.postqc_command:
            queue_job.delete()
        else:
            queue_job.status = 'Ready' if queue_job.alignment_command else 'Pending'
            queue_job.save()


def _finalize_failure(queue_job, running_job):
    """Roll back a failed submission: drop the RunningJob claim and return the
    queue row to a processable (Ready) state."""
    with transaction.atomic():
        try:
            running_job.delete()
        except Exception:
            logger.debug("RunningJob already gone during rollback", exc_info=True)
        try:
            queue_job.refresh_from_db()
            queue_job.status = 'Ready'
            queue_job.save()
        except Exception:
            logger.debug("Could not reset queue job during rollback", exc_info=True)


def _submit_queue_job(queue_job, demand_type, command):
    """Run a single queue command (outside any DB lock) and persist the result.

    Returns a result dict with a ``status`` of 'success' or 'error'.
    """
    fastq_name = queue_job.fastq_name
    running_job = RunningJob.objects.get(fastq_name=fastq_name)

    logger.info("Executing queue command for %s: %s", fastq_name, command)
    try:
        script_path = create_bash_script(command, f'process_queue_{fastq_name}.sh')
        output = run_bash_script(script_path)
    except Exception as cmd_error:
        logger.exception("Command execution error for %s", fastq_name)
        _finalize_failure(queue_job, running_job)
        return {'status': 'error', 'message': f'Error executing command: {cmd_error}'}

    demand_id = _parse_demand_id(output)
    if demand_id is None:
        _finalize_failure(queue_job, running_job)
        return {
            'status': 'error',
            'message': f'Job submission failed: {output}',
            'command_output': output,
        }

    _finalize_success(queue_job, running_job, demand_type, demand_id)
    return {
        'status': 'success',
        'message': f'Successfully started processing job: {fastq_name}',
        'demand_id': demand_id,
        'command': command,
        'demand_type': demand_type,
    }


def seconds_until_next_process(control):
    """Seconds until the global timer fires, or None when the queue is not running.

    Zero means the timer has elapsed and the next backend tick will submit a job.
    """
    if control.state != QueueControl.STATE_RUNNING:
        return None
    if not control.last_processed_at:
        return 0
    elapsed = (timezone.now() - control.last_processed_at).total_seconds()
    return max(0, int(control.interval_minutes * 60 - elapsed))


def process_next_queue_job():
    """Claim and submit the oldest Ready job in the shared queue.

    Uses a row-level lock so the cron processor and a superuser "push" can never
    submit the same job twice. Returns a result dict; status 'idle' means there
    was nothing to do (empty queue or the running-job cap was reached).
    """
    if count_running_jobs().get('total', 0) >= MAX_RUNNING_JOBS:
        return {'status': 'idle', 'message': 'Running-job cap reached'}

    with transaction.atomic():
        queue_job = (
            QueueJobs.objects
            .select_for_update(skip_locked=True)
            .filter(status__in=['Ready', 'ready', 'Pending', 'pending'])
            .order_by('time')
            .first()
        )
        if not queue_job:
            return {'status': 'idle', 'message': 'No Ready jobs available'}

        if RunningJob.objects.filter(fastq_name=queue_job.fastq_name).exists():
            return {
                'status': 'warning',
                'message': f'Job {queue_job.fastq_name} is already running',
                'already_running': True,
            }

        if queue_job.alignment_command:
            command, demand_type = queue_job.alignment_command, 'alignment'
        elif queue_job.postqc_command:
            command, demand_type = queue_job.postqc_command, 'postqc'
        else:
            return {
                'status': 'error',
                'message': f'No valid command found for {queue_job.fastq_name}',
            }

        # Claim the job before releasing the lock so nothing else can take it.
        queue_job.status = 'PROCESSING'
        queue_job.save()
        RunningJob.objects.create(
            fastq_name=queue_job.fastq_name,
            alignment_command=queue_job.alignment_command,
            postqc_command=queue_job.postqc_command,
            time=timezone.now(),
            alignment_attempts=1 if demand_type == 'alignment' else 0,
            postqc_attempts=1 if demand_type == 'postqc' else 0,
        )

    # Execute the command outside the transaction to avoid holding locks.
    result = _submit_queue_job(queue_job, demand_type, command)

    # A successful submission restarts the shared global timer.
    if result.get('status') == 'success':
        control = QueueControl.get()
        control.last_processed_at = timezone.now()
        control.save()

    return result


# ---------------------------------------------------------------------------
# Endpoints available to all authenticated users
# ---------------------------------------------------------------------------

@login_required
def import_queue(request):
    """Add the current user's jobs to the shared queue."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    try:
        data = json.loads(request.body)
        queue_entries = data.get('queue', [])
        for entry in queue_entries:
            QueueJobs.objects.update_or_create(
                fastq_name=entry.get('Fastq Name'),
                defaults={
                    'alignment_command': entry.get('Alignment Command', ''),
                    'postqc_command': entry.get('PostQC Command', ''),
                    'time': timezone.now(),
                    'status': entry.get('Status', 'pending'),
                    'user': request.user,
                },
            )
        return JsonResponse({'status': 'success', 'imported': len(queue_entries)})
    except Exception as e:
        logger.exception("Error importing queue entries")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def get_queue_data(request):
    """Return the full shared queue, with ownership info for the current user."""
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

    try:
        unified_queue = []
        for entry in QueueJobs.objects.select_related('user').all():
            time_val = entry.time.isoformat() if entry.time else None
            base = {
                'fastq_name': entry.fastq_name,
                'time': time_val,
                'queued_at': time_val,
                'submitted_at': time_val,
                'priority': 'Normal',
                'owner': entry.user.username if entry.user else None,
                'is_owner': bool(entry.user_id) and entry.user_id == request.user.id,
            }
            status = entry.status or ''

            # If both commands are present and pending, split into two rows.
            if entry.alignment_command and entry.postqc_command and status.lower() == 'pending':
                unified_queue.append({**base, 'command': entry.alignment_command,
                                      'command_source': 'alignment_command', 'status': 'Ready'})
                unified_queue.append({**base, 'command': entry.postqc_command,
                                      'command_source': 'postqc_command', 'status': 'Pending'})
            else:
                command = entry.alignment_command or entry.postqc_command or 'N/A'
                command_source = ('alignment_command' if entry.alignment_command
                                  else 'postqc_command' if entry.postqc_command else 'unknown')
                unified_queue.append({**base, 'command': command,
                                      'command_source': command_source, 'status': status})

        # Sort by status priority (Ready, then Pending, then others), oldest first.
        def get_status_priority(job):
            s = job['status'].lower()
            return 0 if s == 'ready' else 1 if s == 'pending' else 2

        unified_queue.sort(key=lambda job: (get_status_priority(job), job['time'] or ''))

        control = QueueControl.get()
        return JsonResponse({
            'status': 'success',
            'queue': unified_queue,
            'total_entries': len(unified_queue),
            'queue_state': control.state,
            'interval_minutes': control.interval_minutes,
            'next_process_in_seconds': seconds_until_next_process(control),
            'is_superuser': request.user.is_superuser,
        })
    except Exception as e:
        logger.exception("Error in get_queue_data")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def remove_queue_item(request):
    """Remove a single queue item. Regular users may remove only their own;
    superusers may remove any."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    try:
        item_id = json.loads(request.body).get('id')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    if not item_id:
        return JsonResponse({'status': 'error', 'message': 'Item ID is required'}, status=400)

    try:
        queue_item = QueueJobs.objects.get(fastq_name=item_id)
    except QueueJobs.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': f'Item with ID {item_id} not found'}, status=404)

    if not request.user.is_superuser and queue_item.user_id != request.user.id:
        return JsonResponse(
            {'status': 'error', 'message': 'You can only remove your own queued jobs'},
            status=403,
        )

    queue_item.delete()
    return JsonResponse({
        'status': 'success',
        'message': f'Item {item_id} removed successfully',
        'removed_id': item_id,
    })


@login_required
def remove_multiple_queue_items(request):
    """Remove multiple queue items. Regular users only affect their own jobs;
    superusers affect any."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    item_ids = data.get('ids', []) or data.get('fastq_names', [])
    if not item_ids:
        return JsonResponse({'status': 'error', 'message': 'No item IDs provided'}, status=400)

    queue_items = QueueJobs.objects.filter(fastq_name__in=item_ids)
    if not request.user.is_superuser:
        queue_items = queue_items.filter(user_id=request.user.id)

    count = queue_items.count()
    queue_items.delete()
    return JsonResponse({
        'status': 'success',
        'message': f'{count} items removed successfully',
        'removed_count': count,
    })


# ---------------------------------------------------------------------------
# Superuser-only master controls
# ---------------------------------------------------------------------------

@superuser_required
def process_queue(request):
    """Manually process (push) the next job in the shared queue.

    The backend chooses the next Ready job; the client no longer specifies one.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        return JsonResponse(process_next_queue_job())
    except Exception as e:
        logger.exception("Unexpected error in process_queue")
        return JsonResponse({'status': 'error', 'message': f'Unexpected error: {e}'}, status=500)


@superuser_required
def clear_queue(request):
    """Remove every item from the shared queue."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    try:
        count = QueueJobs.objects.count()
        QueueJobs.objects.all().delete()
        return JsonResponse({
            'status': 'success',
            'message': f'Queue cleared successfully ({count} items removed)',
            'removed_count': count,
        })
    except Exception as e:
        logger.exception("Error clearing queue")
        return JsonResponse({'status': 'error', 'message': f'Error clearing queue: {e}'}, status=500)


@superuser_required
def queue_control(request):
    """Pause, resume, stop, reset, or set the interval of the backend processor."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        data = {}
    action = data.get('action')

    control = QueueControl.get()

    if action == 'set_interval':
        try:
            minutes = int(data.get('minutes'))
        except (TypeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'minutes must be a number'}, status=400)
        if not 1 <= minutes <= 60:
            return JsonResponse({'status': 'error', 'message': 'minutes must be between 1 and 60'}, status=400)
        control.interval_minutes = minutes
        # Restart the global timer so the countdown begins fresh at the new interval.
        control.last_processed_at = timezone.now()
        control.updated_by = request.user
        control.save()
        return JsonResponse({'status': 'success', 'state': control.state, 'interval_minutes': minutes})

    if action == 'pause':
        control.state = QueueControl.STATE_PAUSED
    elif action == 'resume':
        control.state = QueueControl.STATE_RUNNING
    elif action == 'stop':
        control.state = QueueControl.STATE_STOPPED
    elif action == 'reset':
        # Requeue anything stuck mid-processing and resume the processor.
        QueueJobs.objects.filter(status='PROCESSING').update(status='Ready')
        control.state = QueueControl.STATE_RUNNING
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

    control.updated_by = request.user
    control.save()
    return JsonResponse({'status': 'success', 'state': control.state,
                         'interval_minutes': control.interval_minutes})


@superuser_required
def move_queue_item(request):
    """Reorder a Ready job up or down in the shared queue (superuser only)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    try:
        data = json.loads(request.body)
        fastq_name = data.get('fastq_name')
        direction = data.get('direction')  # 'up' or 'down'

        if not fastq_name or not direction:
            return JsonResponse({'status': 'error', 'message': 'fastq_name and direction are required'}, status=400)
        if direction not in ['up', 'down']:
            return JsonResponse({'status': 'error', 'message': 'direction must be "up" or "down"'}, status=400)

        try:
            queue_item = QueueJobs.objects.get(fastq_name=fastq_name)
        except QueueJobs.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Queue item {fastq_name} not found'}, status=404)

        if queue_item.status.lower() not in ['ready', 'pending']:
            return JsonResponse({'status': 'warning',
                                 'message': f'Cannot move job {fastq_name} - only Ready jobs can be reordered'})

        # Processing order is oldest-first, so reordering means swapping timestamps.
        ready_jobs = list(QueueJobs.objects.filter(
            status__in=['Ready', 'ready', 'pending', 'Pending']
        ).order_by('time'))

        if len(ready_jobs) <= 1:
            return JsonResponse({'status': 'warning', 'message': 'Cannot move - only one Ready job in queue'})

        current_index = next((i for i, job in enumerate(ready_jobs) if job.fastq_name == fastq_name), None)
        if current_index is None:
            return JsonResponse({'status': 'error', 'message': f'Job {fastq_name} not found in Ready jobs list'})

        if direction == 'up' and current_index == 0:
            return JsonResponse({'status': 'warning', 'message': f'Job {fastq_name} is already at the top of the queue'})
        if direction == 'down' and current_index == len(ready_jobs) - 1:
            return JsonResponse({'status': 'warning', 'message': f'Job {fastq_name} is already at the bottom of the queue'})

        new_index = current_index - 1 if direction == 'up' else current_index + 1
        swap_job = ready_jobs[new_index]

        queue_item.time, swap_job.time = swap_job.time, queue_item.time
        queue_item.save()
        swap_job.save()

        return JsonResponse({
            'status': 'success',
            'message': f'Successfully moved {fastq_name} {direction} in queue',
            'moved_job': fastq_name,
            'swapped_with': swap_job.fastq_name,
            'direction': direction,
        })
    except Exception as e:
        logger.exception("Error moving queue item")
        return JsonResponse({'status': 'error', 'message': f'Error moving queue item: {e}'}, status=500)
