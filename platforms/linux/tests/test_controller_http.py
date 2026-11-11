import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import HTTPServer
from phoenix_linux.controller import Controller, Unavailable
from phoenix_linux.server import handler
from phoenix_linux.runtime import Runtime
from test_runtime import FakeRunner
from test_policy import BASE, NAMES
from test_vpn import PROFILE


class ControllerTests(unittest.TestCase):
    def test_uninitialized_refuses_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = Controller(tmp, [])
            with self.assertRaises(Unavailable):
                c.save_policy(BASE)
            self.assertEqual(c.store.load()['revision'], 0)

    def test_handshake_history_restart_and_no_api_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = Controller(tmp, [], Runtime(NAMES, FakeRunner(), clock=lambda: 1010))
            c.command({'action': 'wireguard', 'profile': PROFILE})
            self.assertNotIn('private_key', json.dumps(c.vpn_status()))
            c.tick()
            c.tick()
            self.assertEqual(len(c.history.page()['entries']), 1)
            restarted = Controller(tmp, [], Runtime(NAMES, FakeRunner()))
            self.assertFalse(restarted.enabled)
            self.assertEqual(restarted.runtime.mode, 'blocked')
            self.assertEqual(restarted.settings['profile'], PROFILE)
            restarted.command({'action': 'forget'})
            self.assertNotIn('profile', Path(tmp, 'vpn-private.json').read_text())


    def test_retry_backoff_stays_blocked_and_disconnect_cancels(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            runner = FakeRunner(fail=['ip', 'link', 'add', 'phwg0', 'type', 'wireguard'])
            c = Controller(tmp, [], Runtime(NAMES, runner))
            c.settings = {'provider': 'wireguard', 'profile': PROFILE}
            c.want_connected = True
            c.retry_at = 0
            with patch('phoenix_linux.controller.time.monotonic', return_value=100):
                c.tick()
            self.assertEqual(c.runtime.mode, 'blocked')
            self.assertEqual(c.retry_at, 105)
            self.assertFalse(c.enabled)
            c.command({'action': 'disconnect'})
            self.assertIsNone(c.retry_at)
            self.assertFalse(c.want_connected)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.controller = Controller(self.tmp.name, [])
        self.token = 'a' * 64
        self.server = HTTPServer(('127.0.0.1', 0), handler(self.controller, self.token))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.tmp.cleanup()

    def request(self, path, method='GET', body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        status, data = response.status, response.read()
        connection.close()
        return status, data

    def test_auth_and_unavailable_status(self):
        self.assertEqual(self.request('/api/v1/policy')[0], 401)
        headers = {'Authorization': 'Bearer ' + self.token}
        self.assertEqual(self.request('/api/v1/policy', headers=headers)[0], 200)
        self.assertEqual(self.request('/api/v1/status', headers=headers)[0], 503)
        headers['Origin'] = 'https://untrusted.example'
        self.assertEqual(self.request('/api/v1/policy', headers=headers)[0], 403)

    def test_shared_assets_and_traversal(self):
        code, data = self.request('/')
        self.assertEqual(code, 200)
        self.assertIn(b'phoenix', data.lower())
        self.assertEqual(self.request('/../../AGENTS.md')[0], 401)

    def test_invalid_json_and_unsupported_operation(self):
        headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'}
        self.assertEqual(self.request('/api/v1/policy', 'POST', '{"revision":0,"revision":1}', headers)[0], 400)
        self.assertEqual(self.request('/api/v1/firmware', 'POST', '{}', headers)[0], 501)

    def test_duplicate_auth_headers_and_browser_policy(self):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        connection.putrequest('GET','/api/v1/policy')
        connection.putheader('Authorization','Bearer '+self.token)
        connection.putheader('Authorization','Bearer '+'b'*64)
        connection.endheaders()
        response=connection.getresponse()
        self.assertEqual(response.status,400)
        response.read();connection.close()
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        connection.request('GET','/')
        response=connection.getresponse()
        self.assertIn("script-src 'self'",response.getheader('Content-Security-Policy'))
        self.assertEqual(response.getheader('Referrer-Policy'),'no-referrer')
        response.read();connection.close()
