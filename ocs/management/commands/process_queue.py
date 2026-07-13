from django.core.management.base import BaseCommand
from django.utils import timezone

from ocs.models import QueueControl
from ocs.queue_views import process_next_queue_job


class Command(BaseCommand):
    help = ('Submit the next queued job when the shared global timer elapses. '
            'Run this every minute on a schedule (cron).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Ignore the interval timer and submit one job now (if running).',
        )

    def handle(self, *args, **options):
        control = QueueControl.get()

        if control.state != QueueControl.STATE_RUNNING:
            self.stdout.write(f'Queue is {control.state}; nothing submitted.')
            return

        # Global timer: only submit once the interval has elapsed.
        if not options['force'] and control.last_processed_at:
            elapsed = (timezone.now() - control.last_processed_at).total_seconds()
            remaining = control.interval_minutes * 60 - elapsed
            if remaining > 0:
                self.stdout.write(f'Timer not elapsed; {int(remaining)}s remaining.')
                return

        # process_next_queue_job submits a single job and, on success, restarts
        # the global timer (sets last_processed_at).
        result = process_next_queue_job()
        status = result.get('status')
        if status == 'success':
            self.stdout.write(self.style.SUCCESS(
                f"Submitted {result.get('demand_type')} job ({result.get('demand_id')})."))
        elif status == 'idle':
            self.stdout.write(result.get('message', 'Queue idle.'))
        else:
            self.stdout.write(self.style.WARNING(result.get('message', 'Nothing submitted.')))
