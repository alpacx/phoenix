import http.client
from http.server import HTTPServer
import os
import socket
import threading
import unittest
from unittest.mock import MagicMock, patch
from phoenix_linux import usb_admin
from phoenix_linux.server import handler
from phoenix_linux.rpc import RemoteAPI


class UsbAdminTests(unittest.TestCase):
    def request(self, server, method, path, headers):
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        try:
            client = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            client.request(method, path, headers=headers)
            response = client.getresponse()
            result = response.status, dict(response.getheaders()), response.read()
            client.close()
            return result
        finally:
            thread.join(5)

    def test_redirect_fixed_destination_and_no_http_api(self):
        with HTTPServer(('127.0.0.1', 0), usb_admin.Redirect) as server:
            status, headers, _ = self.request(server, 'GET', '//evil.test/?token=secret', {'Host': 'evil.test'})
            self.assertEqual(status, 308)
            self.assertEqual(headers['Location'], 'https://192.168.7.1/')
            self.assertEqual(self.request(server, 'POST', '/api/v1/vpn', {})[0], 405)

    def test_direct_api_requires_token_and_exact_origin(self):
        api = RemoteAPI('/unused')
        with HTTPServer(('127.0.0.1', 0), handler(api, 'a' * 64)) as server:
            server.authority, server.tls = '192.168.7.1', True
            headers = {'Host': '192.168.7.1'}
            self.assertEqual(self.request(server, 'GET', '/api/v1/status', headers)[0], 401)
            headers['Authorization'] = 'Bearer ' + 'a' * 64
            headers['Origin'] = 'http://192.168.7.1'
            self.assertEqual(self.request(server, 'GET', '/api/v1/status', headers)[0], 403)
            headers['Origin'] = 'https://192.168.7.1'
            with patch.object(api, 'call', return_value={'test': True}):
                self.assertEqual(self.request(server, 'GET', '/api/v1/status', headers)[0], 200)
            headers['Host'] = 'evil.test'
            self.assertEqual(self.request(server, 'GET', '/api/v1/status', headers)[0], 403)

    def test_activation_requires_systemd_and_usb_bound_socket(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                usb_admin.activated_server(MagicMock(), MagicMock(), 443)
        for device, address, listening in [(b'eth0', ('192.168.7.1', 443), 1),
                                           (b'phusb0', ('0.0.0.0', 443), 1),
                                           (b'phusb0', ('192.168.7.1', 443), 0)]:
            listener = MagicMock(family=socket.AF_INET)
            listener.getsockname.return_value = address
            listener.getsockopt.side_effect = [device, listening]
            with patch.dict(os.environ, LISTEN_PID=str(os.getpid()), LISTEN_FDS='1'), \
                 patch.object(socket, 'SO_BINDTODEVICE', 25, create=True), \
                 patch.object(socket, 'socket', return_value=listener):
                with self.assertRaises(ValueError):
                    usb_admin.activated_server(MagicMock(), MagicMock(), 443)
                listener.close.assert_called_once()
