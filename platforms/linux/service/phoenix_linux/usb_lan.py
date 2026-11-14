"""DHCP-only USB LAN; consumes an explicitly provisioned Phoenix gadget."""
import json
from ipaddress import IPv4Address, ip_network
from pathlib import Path
import shutil
import subprocess
import time
from .firewall import interface
from .lan import AccessPoint
from .runtime import NetworkError
from .usb_gadget import owned_binding


class UsbLan(AccessPoint):
    address = '192.168.7.1/24'

    def __init__(self, name, dns, directory, runner, popen=subprocess.Popen,
                 which=shutil.which, wait=time.sleep, binding=owned_binding):
        self.name = interface(name)
        self.dns = self.default_dns = str(IPv4Address(dns))
        self.directory = Path(directory)
        self.run, self.popen, self.which, self.wait = runner, popen, which, wait
        self.binding = binding
        self.processes = []
        self.added_address = self.active = False

    def check(self):
        if not self.binding(self.name):
            raise NetworkError('usb_phoenix_gadget_not_bound')
        for command in ('ip', 'dnsmasq'):
            if not self.which(command):
                raise NetworkError('usb_missing_tool:' + command)
        if self.which('nmcli'):
            result = self.run(['nmcli', '-g', 'GENERAL.NM-MANAGED', 'device', 'show', self.name])
            if result.stdout.strip().lower() != 'no':
                raise NetworkError('usb_interface_owned_by_networkmanager')
        addresses = json.loads(self.run(['ip', '-j', 'address', 'show', 'dev', self.name]).stdout)
        v4 = [(a.get('local'), a.get('prefixlen')) for e in addresses for a in e.get('addr_info', []) if a.get('family') == 'inet']
        if any(a != ('192.168.7.1', 24) for a in v4):
            raise NetworkError('usb_interface_has_existing_address')
        routes = json.loads(self.run(['ip', '-j', '-4', 'route', 'show', 'table', 'all']).stdout)
        for route in routes:
            destination = route.get('dst', 'default')
            if destination in ('default', '0.0.0.0/0') or route.get('dev') == self.name:
                continue
            if ip_network(destination, strict=False).overlaps(ip_network('192.168.7.0/24')):
                raise NetworkError('usb_subnet_conflicts_with_route')
        return bool(v4)

    def healthy(self):
        return self.binding(self.name) and super().healthy()

    def render_configs(self, dns):
        dns = str(IPv4Address(dns))
        return {'dnsmasq.conf': f'''port=0
interface={self.name}
bind-interfaces
dhcp-range=192.168.7.20,192.168.7.200,255.255.255.0,1h
dhcp-option=3,192.168.7.1
dhcp-option=6,{dns}
dhcp-authoritative
'''}

    def daemon_commands(self):
        return [['dnsmasq', '--no-daemon', '--conf-file=' + str(self.directory / 'dnsmasq.conf')]]
