import http.client
import json
import tempfile
import threading
import unittest
from http.server import HTTPServer
from phoenix_linux.controller import Controller
from phoenix_linux.server import handler


class PasswordHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = HTTPServer(('127.0.0.1', 0), handler(Controller(self.tmp.name, []), 'a'*64))
        self.server.password_auth, self.server.tls, self.server.allow_bearer = True, True, False
        self.server.authority = '192.168.7.1'
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()

    def request(self, path, body=None, cookie='', origin='https://192.168.7.1', extra=None):
        client = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = {'Host': '192.168.7.1', 'Origin': origin, 'Content-Type': 'application/json', 'Cookie': cookie}
        headers.update(extra or {})
        client.request('GET' if body is None else 'POST', '/api/v1/'+path, None if body is None else json.dumps(body), headers)
        response = client.getresponse()
        result = response.status, dict(response.getheaders()), json.loads(response.read())
        client.close()
        return result

    def test_password_flow_and_csrf_logout(self):
        self.assertTrue(self.request('auth/status')[2]['password_login'])
        code, headers, value = self.request('auth/login', {'password': 'phoenix'})
        self.assertEqual(code, 200); self.assertNotIn('session', value)
        self.assertIn('Secure; HttpOnly; SameSite=Strict', headers['Set-Cookie'])
        cookie = headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request('policy', cookie=cookie)[0], 401)
        self.assertEqual(self.request('auth/password', {'current_password': 'phoenix', 'new_password': 'test password phrase'}, cookie, origin='https://evil.test')[0], 403)
        code, headers, _ = self.request('auth/password', {'current_password': 'phoenix', 'new_password': 'test password phrase'}, cookie)
        self.assertEqual(code, 200)
        cookie = headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request('policy', cookie=cookie)[0], 200)
        self.request('auth/logout', {}, cookie)
        self.assertEqual(self.request('policy', cookie=cookie)[0], 401)

    def test_lockout_and_usb_token_bypass_rejected(self):
        for _ in range(3):
            code, headers, _ = self.request('auth/login', {'password': 'wrong'})
        self.assertEqual(code, 429); self.assertEqual(headers['Retry-After'], '300')
        self.assertEqual(self.request('auth/login', {'password': 'phoenix'})[0], 429)
        self.assertEqual(self.request('policy', extra={'Authorization': 'Bearer '+'a'*64})[0], 401)
        self.assertEqual(self.request('auth/login', {'password': 'phoenix'}, origin='')[0], 403)
