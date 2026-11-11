import unittest
from unittest.mock import patch, MagicMock
from phoenix_linux import uplink_http, nord


class UplinkHTTPTests(unittest.TestCase):
    def test_dns_and_api_bound_to_same_uplink(self):
        connections = []
        def connection(host, address, device, mark):
            connections.append((host, address, device, mark))
            return object()
        with patch.object(uplink_http, 'BoundHTTPS', side_effect=connection), patch.object(uplink_http, 'read_json', side_effect=[{'Status':0,'Answer':[{'type':1,'data':'192.0.2.20'}]}, {'ok':True}]):
            self.assertEqual(uplink_http.get('/v1/test', {}, 'wlan1', 0x5048), {'ok':True})
        self.assertEqual(connections, [('1.1.1.1','1.1.1.1','wlan1',0x5048),('api.nordvpn.com','192.0.2.20','wlan1',0x5048)])

    def test_dns_failure_does_not_request_api_or_use_system_resolver(self):
        with patch.object(uplink_http, 'BoundHTTPS') as connection, patch.object(uplink_http, 'read_json', return_value={'Status':2}), patch('socket.getaddrinfo') as resolver:
            with self.assertRaises(ValueError):
                uplink_http.get('/v1/test', {}, 'wlan1', 0x5048)
            self.assertEqual(connection.call_count, 1)
            resolver.assert_not_called()

    def test_socket_binding_and_tls_server_identity(self):
        raw, context = MagicMock(), MagicMock()
        with patch('socket.socket', return_value=raw):
            c = uplink_http.BoundHTTPS('api.nordvpn.com','192.0.2.20','wlan1',0x5048,context)
            c.connect()
        raw.connect.assert_called_once_with(('192.0.2.20',443))
        context.wrap_socket.assert_called_once_with(raw,server_hostname='api.nordvpn.com')
        self.assertEqual(raw.setsockopt.call_count,2)

    def test_provider_never_returns_sensitive_exception(self):
        with self.assertRaisesRegex(ValueError,'^nord_api_failed$'):
            nord.get('/v1/test', 'secret-test-only', transport=MagicMock(side_effect=RuntimeError('secret-test-only')))
