import json
from pathlib import Path
import tempfile
import unittest
from phoenix_linux.admin_auth import AdminAuth


class PasswordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1000
        self.auth = AdminAuth(self.tmp.name, lambda: self.now)

    def tearDown(self):
        self.tmp.cleanup()

    def test_initial_session_cannot_admin_and_change_revokes_all_sessions(self):
        first = self.auth.call('login', {'password': 'phoenix'})
        second = self.auth.call('login', {'password': 'phoenix'})
        self.assertTrue(first['must_change'])
        self.assertFalse(self.auth.call('check', first)['ok'])
        result = self.auth.call('password', {**first, 'current_password': 'phoenix', 'new_password': 'a long test phrase'})
        self.assertTrue(self.auth.call('check', result)['ok'])
        self.assertFalse(self.auth.call('check', second)['ok'])
        self.assertFalse(self.auth.call('login', {'password': 'phoenix'})['ok'])
        self.assertTrue(self.auth.call('login', {'password': 'a long test phrase'})['ok'])
        stored = (Path(self.tmp.name) / 'admin-password.json').read_text()
        self.assertNotIn('a long test phrase', stored)
        self.assertNotIn('phoenix', stored)
        self.assertEqual((Path(self.tmp.name) / 'admin-password.json').stat().st_mode & 0o777, 0o600)

    def test_third_failure_locks_even_correct_password_and_survives_restart(self):
        for _ in range(2):
            self.assertEqual(self.auth.call('login', {'password': 'wrong'})['error'], 'invalid_password')
        result = self.auth.call('login', {'password': 'wrong'})
        self.assertEqual(result['retry_after'], 300)
        self.auth = AdminAuth(self.tmp.name, lambda: self.now)
        self.assertEqual(self.auth.call('login', {'password': 'phoenix'})['error'], 'login_locked')
        self.now += 300
        self.assertTrue(self.auth.call('login', {'password': 'phoenix'})['ok'])

    def test_session_expiry_logout_and_restart(self):
        result = self.auth.call('login', {'password': 'phoenix'})
        self.now += 601
        self.assertFalse(self.auth.call('status', result)['authenticated'])
        result = self.auth.call('login', {'password': 'phoenix'})
        self.auth.call('logout', result)
        self.assertFalse(self.auth.call('status', result)['authenticated'])
        result = self.auth.call('login', {'password': 'phoenix'})
        self.auth = AdminAuth(self.tmp.name, lambda: self.now)
        self.assertFalse(self.auth.call('status', result)['authenticated'])

    def test_change_requires_session_current_password_and_length(self):
        self.assertFalse(self.auth.call('password', {'new_password': 'a long test phrase'})['ok'])
        session = self.auth.call('login', {'password': 'phoenix'})
        self.assertFalse(self.auth.call('password', {**session, 'current_password': 'phoenix', 'new_password': 'short'})['ok'])
        for _ in range(3):
            result = self.auth.call('password', {**session, 'current_password': 'wrong', 'new_password': 'a long test phrase'})
        self.assertEqual(result['error'], 'login_locked')
