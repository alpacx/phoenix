"""Bound HTTPS for provisioning: DNS and TLS use only the selected uplink.

DNS bootstrap uses authenticated DoH at a numeric address, so it never consults
host resolv.conf. No proxies, redirects, alternate interfaces or TLS bypass.
"""
import http.client
from ipaddress import IPv4Address
import json
import socket
import ssl
from urllib.parse import urlencode
from .firewall import interface


class BoundHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, device, mark=0, context=None, port=443):
        super().__init__(host, port=port, timeout=12, context=context or ssl.create_default_context())
        self.address, self.device, self.mark = str(IPv4Address(address)), interface(device), mark

    def connect(self):
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            raw.settimeout(self.timeout)
            raw.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, self.device.encode() + b'\0')
            if self.mark:
                raw.setsockopt(socket.SOL_SOCKET, socket.SO_MARK, self.mark)
            raw.connect((self.address, self.port))
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def read_json(connection, path, headers):
    try:
        connection.request('GET', path, headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('https_status_rejected')
        data = response.read(262145)
        if len(data) > 262144:
            raise ValueError('https_response_too_large')
        return json.loads(data)
    finally:
        connection.close()


def get(path, headers, device, mark=0):
    if not path.startswith('/v1/') or any(ord(c) < 32 for c in path):
        raise ValueError('invalid_api_path')
    dns = read_json(BoundHTTPS('1.1.1.1', '1.1.1.1', device, mark),
                    '/dns-query?' + urlencode({'name': 'api.nordvpn.com', 'type': 'A'}),
                    {'Accept': 'application/dns-json'})
    if not isinstance(dns, dict) or dns.get('Status') != 0:
        raise ValueError('uplink_dns_failed')
    answers = dns.get('Answer', [])
    addresses = [str(IPv4Address(a['data'])) for a in answers if a.get('type') == 1]
    if not addresses:
        raise ValueError('uplink_dns_failed')
    # TLS still authenticates api.nordvpn.com; a DNS result is not a trust anchor.
    return read_json(BoundHTTPS('api.nordvpn.com', addresses[0], device, mark), path, headers)
