"""Optional target AP lifecycle: owns only explicitly assigned interface/processes.

NetworkManager ownership must be relinquished explicitly outside this service.
No system-wide daemon is stopped. Tests may inject command/process adapters.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from .access_point import render
from .firewall import interface
from .runtime import NetworkError


class AccessPoint:
    address = '192.168.9.1/24'

    def __init__(self, name, ssid, password, country, dns, directory, runner,
                 popen=subprocess.Popen, which=shutil.which, wait=time.sleep):
        self.name = interface(name)
        self.ssid, self.password, self.country, self.dns = ssid, password, country, dns
        render(name, ssid, password, country, dns)
        self.directory = Path(directory)
        self.run, self.popen, self.which, self.wait = runner, popen, which, wait
        self.default_dns = dns
        self.processes = []
        self.added_address = False
        self.active = False

    def check(self):
        for command in ('ip', 'iw', 'hostapd', 'dnsmasq'):
            if not self.which(command):
                raise NetworkError('ap_missing_tool:' + command)
        if self.which('nmcli'):
            result = self.run(['nmcli', '-g', 'GENERAL.NM-MANAGED', 'device', 'show', self.name])
            if result.stdout.strip().lower() != 'no':
                raise NetworkError('ap_interface_owned_by_networkmanager')
        info = self.run(['iw', 'dev', self.name, 'info']).stdout
        match = re.search(r'^\s*wiphy (\d+)\s*$', info, re.MULTILINE)
        if not match:
            raise NetworkError('ap_wiphy_not_found')
        phy = self.run(['iw', 'phy', 'phy' + match.group(1), 'info']).stdout
        if not re.search(r'^\s*\* AP\s*$', phy, re.MULTILINE):
            raise NetworkError('ap_mode_not_supported')
        addresses = json.loads(self.run(['ip', '-j', 'address', 'show', 'dev', self.name]).stdout)
        v4 = [(a.get('local'), a.get('prefixlen')) for entry in addresses for a in entry.get('addr_info', []) if a.get('family') == 'inet']
        if any(address != ('192.168.9.1', 24) for address in v4):
            raise NetworkError('ap_interface_has_existing_address')
        return bool(v4)

    def render_configs(self, dns):
        configs = render(self.name, self.ssid, self.password, self.country, dns)
        configs['hostapd.conf'] += 'ignore_broadcast_ssid=0\nctrl_interface=' + str(self.directory / 'control') + '\n'
        return configs

    def daemon_commands(self):
        return [['hostapd', str(self.directory / 'hostapd.conf')],
                ['dnsmasq', '--no-daemon', '--conf-file=' + str(self.directory / 'dnsmasq.conf')]]

    def write_configs(self, dns):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink() or self.directory.stat().st_uid != os.getuid() or self.directory.stat().st_mode & 0o077:
            raise ValueError('ap_state_directory_not_private')
        configs = self.render_configs(dns)
        configs['dnsmasq.conf'] += 'dhcp-leasefile=' + str(self.directory / 'leases') + '\n'
        for name, data in configs.items():
            path = self.directory / name
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as stream:
                stream.write(data)
        self.run(['dnsmasq', '--test', '--conf-file=' + str(self.directory / 'dnsmasq.conf')])

    def spawn(self, argv):
        process = self.popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True)
        self.processes.append(process)
        self.wait(0.25)
        if process.poll() is not None:
            raise NetworkError('ap_daemon_start_failed')
        return process

    def start(self):
        if self.active:
            raise NetworkError('ap_already_active')
        existing = self.check()
        self.write_configs(self.dns)
        try:
            if not existing:
                self.run(['ip', 'address', 'add', self.address, 'dev', self.name])
                self.added_address = True
            self.run(['ip', 'link', 'set', 'dev', self.name, 'up'])
            for command in self.daemon_commands():
                self.spawn(command)
            self.active = True
        except Exception:
            self.stop()
            raise

    def set_dns(self, dns):
        if dns == self.dns:
            return
        self.write_configs(dns)
        if self.active:
            process = self.processes.pop()
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=3)
            self.spawn(['dnsmasq', '--no-daemon', '--conf-file=' + str(self.directory / 'dnsmasq.conf')])
        self.dns = dns

    def radio_status(self):
        if not self.active:
            return {'state': 'DISABLED', 'clients': 0}
        try:
            if not self.which('hostapd_cli'):
                return {'state': 'UNKNOWN', 'clients': None}
            output = self.run(['hostapd_cli', '-p', str(self.directory / 'control'),
                               '-i', self.name, 'status']).stdout
            fields = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
            return {'state': fields.get('state', 'UNKNOWN'),
                    'clients': int(fields['num_sta[0]']) if 'num_sta[0]' in fields else None}
        except Exception:
            return {'state': 'UNKNOWN', 'clients': None}

    def healthy(self):
        return self.active and len(self.processes) == len(self.daemon_commands()) and all(process.poll() is None for process in self.processes)

    def stop(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
        self.processes.clear()
        if self.added_address:
            self.run(['ip', 'address', 'del', self.address, 'dev', self.name], optional=True)
            self.added_address = False
        self.active = False
