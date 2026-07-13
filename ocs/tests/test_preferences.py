"""Tests for per-user preference sync (cross-device)."""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ocs.models import UserPreferences


class PreferenceSyncTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw')
        self.bob = User.objects.create_user('bob', password='pw')
        self.url = reverse('user_preferences_api')

    def post(self, payload):
        return self.client.post(self.url, data=json.dumps(payload),
                                content_type='application/json')

    def test_get_is_empty_for_new_user(self):
        self.client.force_login(self.alice)
        body = self.client.get(self.url).json()
        self.assertEqual(body, {'column_settings': {}, 'filter_preferences': {}})

    def test_save_then_load(self):
        self.client.force_login(self.alice)
        cols = {'fastq_name': True, 'organism': False}
        filters = {'searchTerm': 'rtx', 'activeFilters': {'study_set': ['S1']}, 'filterMode': 'manual'}
        self.assertEqual(self.post({'column_settings': cols, 'filter_preferences': filters}).status_code, 200)

        body = self.client.get(self.url).json()
        self.assertEqual(body['column_settings'], cols)
        self.assertEqual(body['filter_preferences'], filters)
        self.assertEqual(UserPreferences.objects.count(), 1)

    def test_preferences_are_per_user(self):
        self.client.force_login(self.alice)
        self.post({'column_settings': {'fastq_name': True}})

        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(self.url).json()['column_settings'], {})

    def test_partial_update_does_not_wipe_other_key(self):
        self.client.force_login(self.alice)
        self.post({'column_settings': {'a': True}, 'filter_preferences': {'searchTerm': 'x'}})
        # Send only columns; filters must remain.
        self.post({'column_settings': {'a': False}})

        body = self.client.get(self.url).json()
        self.assertEqual(body['column_settings'], {'a': False})
        self.assertEqual(body['filter_preferences'], {'searchTerm': 'x'})

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (302, 403))
