"""Strict, script-free WireGuard profile parsing matching Phoenix IPv4 scope."""
import base64
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Interface
import re


def key(value):
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise ValueError('invalid_key') from None
    if len(raw) != 32 or base64.b64encode(raw).decode() != value:
        raise ValueError('invalid_key')
    return value


def number(value, low, high):
    if not re.fullmatch(r'[0-9]+', value) or not low <= int(value) <= high:
        raise ValueError('invalid_number')
    return int(value)


@dataclass(frozen=True)
class Profile:
    private_key: str = field(repr=False)
    public_key: str
    address: str
    dns: str
    endpoint: str
    mtu: int = 1380
    keepalive: int = 0
    preshared_key: str = field(default='', repr=False)

    def setconf(self):
        text = f'[Interface]\nPrivateKey = {self.private_key}\n[Peer]\nPublicKey = {self.public_key}\n'
        if self.preshared_key:
            text += f'PresharedKey = {self.preshared_key}\n'
        return text + f'Endpoint = {self.endpoint}\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = {self.keepalive}\n'


def parse(text):
    if not isinstance(text, str) or not 0 < len(text.encode()) <= 4096 or '\0' in text:
        raise ValueError('invalid_profile')
    sections = {}
    current = None
    allowed = {'Interface': {'PrivateKey', 'Address', 'DNS', 'MTU'},
               'Peer': {'PublicKey', 'PresharedKey', 'Endpoint', 'AllowedIPs', 'PersistentKeepalive'}}
    for line in text.splitlines():
        if len(line.encode()) > 255:
            raise ValueError('line_too_long')
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        if line.startswith('['):
            name = line[1:-1] if line.endswith(']') else ''
            if name not in allowed or name in sections or (name == 'Peer' and 'Interface' not in sections):
                raise ValueError('invalid_section')
            current = sections[name] = {}
            section = name
        else:
            if current is None or '=' not in line:
                raise ValueError('invalid_field')
            name, value = map(str.strip, line.split('=', 1))
            if name not in allowed[section] or name in current:
                raise ValueError('unknown_or_duplicate_field')
            current[name] = value
    try:
        a, b = sections['Interface'], sections['Peer']
        private, public = key(a['PrivateKey']), key(b['PublicKey'])
        if '/' not in a['Address']:
            raise ValueError('prefix_required')
        address = IPv4Interface(a['Address'])
        if address.network.prefixlen == 0:
            raise ValueError('invalid_prefix')
        dns = str(IPv4Address(a['DNS']))
        ip, port = b['Endpoint'].split(':')
        endpoint = f'{IPv4Address(ip)}:{number(port, 1, 65535)}'
        if b['AllowedIPs'] != '0.0.0.0/0':
            raise ValueError('full_tunnel_required')
        return Profile(private, public, str(address), dns, endpoint,
                       number(a.get('MTU', '1380'), 1280, 1420),
                       number(b.get('PersistentKeepalive', '0'), 0, 65535),
                       key(b['PresharedKey']) if 'PresharedKey' in b else '')
    except (KeyError, TypeError):
        raise ValueError('missing_profile_fields') from None
