"""Opt-in NetworkManager STA adapter. Secrets never appear in command arguments.

Only a Phoenix-owned connection is replaced. Arbitrary active connections are
not disconnected. Uses keyfiles supported by both Bullseye and Bookworm.
"""
import os
from pathlib import Path
import re
import uuid
from ipaddress import IPv4Address
from .firewall import interface
from .vault import Vault
from .runtime import NetworkError


def validate(body):
    if not isinstance(body, dict) or body.get('mode') != 'sta' or type(body.get('save', False)) is not bool:
        raise ValueError('invalid_wifi_configuration')
    ssid, password = body.get('ssid'), body.get('password', '')
    if not isinstance(ssid, str) or not 1 <= len(ssid.encode()) <= 32 or any(ord(c) < 32 for c in ssid):
        raise ValueError('invalid_ssid')
    if not isinstance(password, str) or (password and (not 8 <= len(password) <= 63 or not password.isascii() or any(ord(c) < 32 for c in password))):
        raise ValueError('invalid_password')


def split_fields(line):
    fields, value, escaped = [], '', False
    for c in line:
        if escaped:
            value += c
            escaped = False
        elif c == '\\':
            escaped = True
        elif c == ':':
            fields.append(value)
            value = ''
        else:
            value += c
    if escaped:
        raise ValueError('invalid_scan_line')
    return fields + [value]


class Station:
    def __init__(self, name, directory, runner, profile_directory=None):
        self.name = interface(name)
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        if self.directory.is_symlink() or self.directory.stat().st_uid != os.getuid() or self.directory.stat().st_mode & 0o077:
            raise ValueError('station_directory_not_private')
        self.profile_directory = Path(profile_directory) if profile_directory else self.directory
        self.profile_directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        if self.profile_directory.is_symlink() or self.profile_directory.stat().st_uid != os.getuid() or self.profile_directory.stat().st_mode & 0o022:
            raise ValueError("unsafe_networkmanager_profile_directory")
        self.run = runner
        self.uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'phoenix://station/' + self.name))
        self.connection_name = 'phoenix-sta-' + self.name
        self.vault = Vault(self.directory)
        self.current = self.vault.load()
        self.active = False

    def scan(self):
        result = self.run(['nmcli', '-t', '--escape', 'yes', '-f', 'SSID,SIGNAL,SECURITY',
                           'device', 'wifi', 'list', 'ifname', self.name, '--rescan', 'yes'])
        networks = []
        for line in result.stdout.splitlines():
            fields = split_fields(line)
            if len(fields) != 3 or not fields[0] or not fields[1].isdigit():
                continue
            networks.append({'ssid': fields[0], 'signal_percent': int(fields[1]),
                             'rssi': None, 'security': fields[2]})
        return {'networks': networks[:16]}

    def check_ownership(self):
        current = self.run(['nmcli', '-g', 'GENERAL.CON-UUID', 'device', 'show', self.name]).stdout.strip()
        if current not in ('', '--', self.uuid):
            raise NetworkError('wifi_interface_has_foreign_connection')
        existing = self.run(['nmcli', '-g', 'connection.id', 'connection', 'show', 'uuid', self.uuid], optional=True)
        if existing.returncode == 0 and existing.stdout.strip() != self.connection_name:
            raise NetworkError('wifi_profile_collision')

    def prepare_startup(self, restore_ap=False):
        # Recover only our connection after a prior process crash; never another profile.
        self.check_ownership()
        current = self.run(['nmcli', '-g', 'GENERAL.CON-UUID', 'device', 'show', self.name]).stdout.strip()
        if current == self.uuid:
            self.run(['nmcli', 'connection', 'down', 'uuid', self.uuid])
        self.active = False
        if restore_ap:
            self.run(['nmcli', 'device', 'set', self.name, 'autoconnect', 'no'])
            self.run(['nmcli', 'device', 'set', self.name, 'managed', 'no'])

    def connect(self, body):
        validate(body)
        self.check_ownership()
        # Decimal SSID bytes are a supported keyfile representation: no keyfile
        # injection, loss of leading spaces, or dependency on nmcli --offline.
        ssid = ''.join(str(byte) + ';' for byte in body['ssid'].encode('utf8'))
        profile = (f'[connection]\nid={self.connection_name}\nuuid={self.uuid}\n'
                   f'type=wifi\ninterface-name={self.name}\nautoconnect=false\n'
                   f'[wifi]\nmode=infrastructure\nssid={ssid}\n'
                   '[ipv4]\nmethod=auto\nnever-default=true\nignore-auto-dns=true\n'
                   '[ipv6]\nmethod=disabled\n')
        if body.get('password'):
            profile += '[wifi-security]\nkey-mgmt=wpa-psk\npsk-flags=2\n'
        config = self.profile_directory / (self.connection_name + '.nmconnection')
        secret = self.directory / 'password'
        def write(path, text):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as stream:
                stream.write(text)
        write(config, profile)
        write(secret, '802-11-wireless-security.psk:' + body.get('password', '') + '\n')
        self.active = False
        try:
            self.run(['nmcli', 'device', 'set', self.name, 'autoconnect', 'no'])
            self.run(['nmcli', 'device', 'set', self.name, 'managed', 'yes'])
            self.run(['nmcli', 'connection', 'load', str(config)])
            self.run(['nmcli', '--wait', '10', 'connection', 'up', 'uuid', self.uuid,
                      'ifname', self.name, 'passwd-file', str(secret)])
            gateway = self.run(['nmcli', '-g', 'IP4.GATEWAY', 'device', 'show', self.name]).stdout.strip().splitlines()
            if not gateway:
                raise NetworkError('wifi_gateway_not_assigned')
            gateway = str(IPv4Address(gateway[0]))
            self.current = dict(body)
            self.vault.save(body if body.get('save') else {})
            self.active = True
            return gateway
        except Exception:
            self.run(['nmcli', 'connection', 'down', 'uuid', self.uuid], optional=True)
            raise
        finally:
            secret.unlink(missing_ok=True)

    def reconnect(self):
        if not self.current:
            raise ValueError('wifi_profile_required')
        return self.connect(self.current)

    def disconnect(self):
        if self.active:
            self.run(['nmcli', 'connection', 'down', 'uuid', self.uuid], optional=True)
            self.active = False
