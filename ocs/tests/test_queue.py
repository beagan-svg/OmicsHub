"""Tests for the shared, permission-based queue.

Covers the required behaviours:
  1. a regular user can view the whole shared queue,
  2. a regular user can add a job,
  3. a regular user can remove their own queued job,
  4. a regular user cannot remove another user's job,
  5. a regular user cannot pause/clear/reset/stop/process/reorder the queue,
  6. a superuser can control the queue,
  7. a superuser can remove or reorder any job.
"""

import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ocs.models import QueueControl, QueueJobs, RunningJob


class QueueTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw')
        self.bob = User.objects.create_user('bob', password='pw')
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pw')

        # Two jobs owned by different users.
        self.alice_job = QueueJobs.objects.create(
            fastq_name='alice_sample', alignment_command='align alice',
            status='Ready', user=self.alice, time=timezone.now(),
        )
        self.bob_job = QueueJobs.objects.create(
            fastq_name='bob_sample', alignment_command='align bob',
            status='Ready', user=self.bob, time=timezone.now(),
        )

    def post(self, name, payload):
        return self.client.post(reverse(name), data=json.dumps(payload),
                                content_type='application/json')

    # 1 -------------------------------------------------------------------
    def test_regular_user_views_full_shared_queue(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse('ocs:get_queue_data'))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        names = {row['fastq_name'] for row in body['queue']}
        self.assertEqual(names, {'alice_sample', 'bob_sample'})
        # Ownership is surfaced so the UI can gate row actions.
        alice_row = next(r for r in body['queue'] if r['fastq_name'] == 'alice_sample')
        bob_row = next(r for r in body['queue'] if r['fastq_name'] == 'bob_sample')
        self.assertTrue(alice_row['is_owner'])
        self.assertFalse(bob_row['is_owner'])
        self.assertEqual(bob_row['owner'], 'bob')
        self.assertFalse(body['is_superuser'])

    # 2 -------------------------------------------------------------------
    def test_regular_user_can_add_job(self):
        self.client.force_login(self.alice)
        response = self.post('ocs:import_queue', {'queue': [{
            'Fastq Name': 'new_sample',
            'Alignment Command': 'align new',
            'Status': 'Ready',
        }]})
        self.assertEqual(response.status_code, 200)
        job = QueueJobs.objects.get(fastq_name='new_sample')
        self.assertEqual(job.user, self.alice)

    # 3 -------------------------------------------------------------------
    def test_regular_user_removes_own_job(self):
        self.client.force_login(self.alice)
        response = self.post('ocs:remove_queue_item', {'id': 'alice_sample'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(QueueJobs.objects.filter(fastq_name='alice_sample').exists())

    # 4 -------------------------------------------------------------------
    def test_regular_user_cannot_remove_others_job(self):
        self.client.force_login(self.alice)
        response = self.post('ocs:remove_queue_item', {'id': 'bob_sample'})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(QueueJobs.objects.filter(fastq_name='bob_sample').exists())

    def test_remove_multiple_only_affects_own_jobs(self):
        self.client.force_login(self.alice)
        response = self.post('ocs:remove_multiple_queue_items',
                             {'ids': ['alice_sample', 'bob_sample']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['removed_count'], 1)
        self.assertFalse(QueueJobs.objects.filter(fastq_name='alice_sample').exists())
        self.assertTrue(QueueJobs.objects.filter(fastq_name='bob_sample').exists())

    # 5 -------------------------------------------------------------------
    def test_regular_user_blocked_from_master_controls(self):
        self.client.force_login(self.alice)
        cases = [
            ('ocs:clear_queue', {}),
            ('ocs:process_queue', {}),
            ('ocs:move_queue_item', {'fastq_name': 'bob_sample', 'direction': 'up'}),
            ('ocs:queue_control', {'action': 'pause'}),
            ('ocs:queue_control', {'action': 'stop'}),
            ('ocs:queue_control', {'action': 'reset'}),
            ('ocs:queue_control', {'action': 'set_interval', 'minutes': 5}),
        ]
        for name, payload in cases:
            with self.subTest(endpoint=name, payload=payload):
                response = self.post(name, payload)
                self.assertEqual(response.status_code, 403)
        # Nothing was changed.
        self.assertEqual(QueueJobs.objects.count(), 2)
        self.assertEqual(QueueControl.get().state, 'running')
        self.assertEqual(QueueControl.get().interval_minutes, 3)

    def test_get_queue_data_includes_timer_info(self):
        self.client.force_login(self.alice)
        body = self.client.get(reverse('ocs:get_queue_data')).json()
        self.assertEqual(body['interval_minutes'], 3)
        # Running with no prior submission => timer already elapsed (0).
        self.assertEqual(body['next_process_in_seconds'], 0)

    def test_superuser_sets_interval(self):
        self.client.force_login(self.admin)
        response = self.post('ocs:queue_control', {'action': 'set_interval', 'minutes': 7})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['interval_minutes'], 7)
        self.assertEqual(QueueControl.get().interval_minutes, 7)
        # Out-of-range values are rejected.
        self.assertEqual(self.post('ocs:queue_control',
                                   {'action': 'set_interval', 'minutes': 999}).status_code, 400)
        self.assertEqual(QueueControl.get().interval_minutes, 7)

    def test_setting_interval_restarts_the_global_timer(self):
        self.client.force_login(self.admin)
        self.post('ocs:queue_control', {'action': 'set_interval', 'minutes': 10})
        body = self.client.get(reverse('ocs:get_queue_data')).json()
        # The countdown restarts at the full new interval (~600s), not 0.
        self.assertGreater(body['next_process_in_seconds'], 590)
        self.assertLessEqual(body['next_process_in_seconds'], 600)

    # 6 -------------------------------------------------------------------
    def test_superuser_controls_queue(self):
        self.client.force_login(self.admin)

        for action, expected in [('pause', 'paused'), ('resume', 'running'),
                                 ('stop', 'stopped'), ('reset', 'running')]:
            with self.subTest(action=action):
                response = self.post('ocs:queue_control', {'action': action})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['state'], expected)
                self.assertEqual(QueueControl.get().state, expected)

        # reset re-queues stuck jobs.
        QueueJobs.objects.filter(fastq_name='alice_sample').update(status='PROCESSING')
        self.post('ocs:queue_control', {'action': 'reset'})
        self.assertEqual(QueueJobs.objects.get(fastq_name='alice_sample').status, 'Ready')

        # clear empties the shared queue.
        response = self.post('ocs:clear_queue', {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(QueueJobs.objects.count(), 0)

    # 7 -------------------------------------------------------------------
    def test_superuser_removes_any_job(self):
        self.client.force_login(self.admin)
        response = self.post('ocs:remove_queue_item', {'id': 'bob_sample'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(QueueJobs.objects.filter(fastq_name='bob_sample').exists())

    def test_superuser_reorders_any_job(self):
        self.client.force_login(self.admin)
        # Make ordering deterministic: alice older than bob.
        old = timezone.now() - timezone.timedelta(hours=1)
        QueueJobs.objects.filter(fastq_name='alice_sample').update(time=old)
        response = self.post('ocs:move_queue_item',
                             {'fastq_name': 'bob_sample', 'direction': 'up'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        # bob is now older (processed first).
        bob_time = QueueJobs.objects.get(fastq_name='bob_sample').time
        alice_time = QueueJobs.objects.get(fastq_name='alice_sample').time
        self.assertLess(bob_time, alice_time)


class QueueProcessorTestCase(TestCase):
    """The backend processor submits the next Ready job (OCS execution mocked)."""

    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pw')
        QueueJobs.objects.create(
            fastq_name='proc_sample', alignment_command='align proc',
            status='Ready', user=self.admin, time=timezone.now(),
        )

    @mock.patch('ocs.queue_views.run_bash_script')
    @mock.patch('ocs.queue_views.create_bash_script', return_value='/tmp/fake.sh')
    @mock.patch('ocs.queue_views.count_running_jobs', return_value={'total': 0})
    def test_process_next_submits_job(self, _counts, _create, run_script):
        run_script.return_value = json.dumps({
            'demand_status': 'SUBMITTED',
            'demand_execution': {'demand_id': 'demand-123'},
        })
        from ocs.queue_views import process_next_queue_job
        result = process_next_queue_job()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['demand_id'], 'demand-123')
        # The alignment command was the only one, so the queue row is consumed
        # and a RunningJob now tracks it.
        self.assertFalse(QueueJobs.objects.filter(fastq_name='proc_sample').exists())
        self.assertTrue(RunningJob.objects.filter(
            fastq_name='proc_sample', alignment_demand_id='demand-123').exists())
        # A successful submission restarts the global timer.
        self.assertIsNotNone(QueueControl.get().last_processed_at)

    def test_command_respects_timer(self):
        from django.core.management import call_command
        control = QueueControl.get()
        control.interval_minutes = 5
        control.last_processed_at = timezone.now()  # just submitted
        control.save()
        # Timer has not elapsed, so the command must not submit (and never shells
        # out to OCS). The job stays queued.
        call_command('process_queue')
        self.assertTrue(QueueJobs.objects.filter(fastq_name='proc_sample').exists())

    @mock.patch('ocs.queue_views.count_running_jobs', return_value={'total': 100})
    def test_processor_idle_when_cap_reached(self, _counts):
        from ocs.queue_views import process_next_queue_job
        result = process_next_queue_job()
        self.assertEqual(result['status'], 'idle')
        self.assertTrue(QueueJobs.objects.filter(fastq_name='proc_sample').exists())
