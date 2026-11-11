"""Linux-only network adapter. Dedicated gateway, never the development host.

All commands are argv lists. No wg-quick hooks, shell scripts, or key arguments.
The adapter owns only the phoenix nft table, phwg0 and policy routing priority
17700/17701 + table 17700. Caller must serialize operations.
"""
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from .firewall import compile_rules, interface


class NetworkError(Exception):
    pass


class Runner:
    def __init__(self):
        if platform.system() != 'Linux' or os.geteuid() != 0:
            raise NetworkError('linux_root_required')

    def __call__(self, argv, data=None, optional=False):
        try:
            result = subprocess.run(argv, input=data, text=True, capture_output=True, timeout=15, env=dict(os.environ, LC_ALL='C'))
        except (OSError, subprocess.SubprocessError):
            raise NetworkError('command_failed:' + argv[0]) from None
        if result.returncode and not optional:
            # Never return stderr: a tool might echo private configuration.
            raise NetworkError('command_failed:' + argv[0])
        return result


class Runtime:
    def __init__(self, interfaces, runner, clock=time.time):
        self.names = {k: interface(interfaces[k]) for k in ('ap', 'usb', 'uplink', 'vpn')}
        if len(set(self.names.values())) != 4 or self.names['vpn'] != 'phwg0':
            raise ValueError('invalid_interface_assignment')
        self.ethernet_name = self.names['uplink']
        self.uplink_kind = 'ethernet'
        self.selected_route = False
        self.run = runner
        self.clock = clock
        self.mode = 'blocked'
        self.profile = None
        self.policy = None
        self.enforced = False

    def firewall(self, policy, mode):
        exists = self.run(['nft', 'list', 'table', 'inet', 'phoenix'], optional=True).returncode == 0
        text = compile_rules(policy, self.names, mode, existing=exists)
        self.run(['nft', '--check', '-f', '-'], data=text)
        self.run(['nft', '-f', '-'], data=text)
        self.mode, self.policy, self.enforced = mode, policy, True

    def block(self, policy):
        self.firewall(policy, 'blocked')
        # Remove old NAT mappings in both directions after the drop barrier.
        for subnet in ('192.168.7.0/24', '192.168.9.0/24'):
            for direction in ('-s', '-d'):
                result = self.run(['conntrack', '-D', '-f', 'ipv4', direction, subnet], optional=True)
                if result.returncode not in (0, 1):
                    raise NetworkError('conntrack_cleanup_failed')

    def connect(self, policy, profile):
        # Install drop before touching routes or the old tunnel; no direct fallback.
        self.block(policy)
        self.profile = None
        try:
            self.run(['ip', 'link', 'delete', 'phwg0'], optional=True)
            self.run(['ip', 'link', 'add', 'phwg0', 'type', 'wireguard'])
            self.run(['wg', 'setconf', 'phwg0', '/dev/stdin'], data=profile.setconf())
            if self.selected_route:
                self.run(['wg', 'set', 'phwg0', 'fwmark', '0x5048'])
            self.run(['ip', 'address', 'add', profile.address, 'dev', 'phwg0'])
            self.run(['ip', 'link', 'set', 'dev', 'phwg0', 'mtu', str(profile.mtu), 'up'])
            self.run(['ip', 'route', 'replace', 'table', '17700', 'default', 'dev', 'phwg0'])
            for offset, role in enumerate(('ap', 'usb')):
                priority = str(17700 + offset)
                self.run(['ip', 'rule', 'del', 'priority', priority], optional=True)
                self.run(['ip', 'rule', 'add', 'priority', priority, 'iif', self.names[role], 'lookup', '17700'])
            self.run(['ip', 'rule', 'del', 'priority', '17702'], optional=True)
            self.run(['ip', 'rule', 'add', 'priority', '17702', 'oif', 'phwg0', 'lookup', '17700'])
            # Endpoint packets originate locally and continue to use the existing uplink route.
            route_command = ['ip', '-j', 'route', 'get', profile.endpoint.split(':')[0]]
            if self.selected_route:
                route_command += ['mark', '0x5048']
            routes = json.loads(self.run(route_command).stdout)
            if not routes or routes[0].get('dev') != self.names['uplink']:
                raise NetworkError('endpoint_route_not_selected_uplink')
            self.profile = profile
            # WG mode sends clients only to phwg0, never plaintext to the uplink.
            self.firewall(policy, 'vpn')
        except Exception:
            self.mode = 'blocked'
            try:
                self.block(policy)
            finally:
                self.run(['ip', 'link', 'delete', 'phwg0'], optional=True)
                self.profile = None
            raise

    def disconnect(self, policy):
        self.block(policy)
        self.run(['ip', 'link', 'delete', 'phwg0'], optional=True)
        for priority in ('17700', '17701', '17702'):
            self.run(['ip', 'rule', 'del', 'priority', priority], optional=True)
        self.profile = None

    def direct(self, policy):
        self.disconnect(policy)
        self.firewall(policy, 'direct')

    def handshake(self):
        profile = self.profile
        if self.mode != 'vpn' or profile is None:
            return False
        result = self.run(['wg', 'show', 'phwg0', 'latest-handshakes'], optional=True)
        if result.returncode:
            return False
        for row in result.stdout.splitlines():
            fields = row.split()
            if len(fields) == 2 and fields[0] == profile.public_key:
                try:
                    age = self.clock() - int(fields[1])
                    return 0 <= age <= 180 and int(fields[1]) > 0
                except ValueError:
                    return False
        return False

    def status(self):
        links = json.loads(self.run(['ip', '-j', 'address', 'show']).stdout)
        by_name = {item['ifname']: item for item in links}
        def link(role):
            item = by_name.get(self.names[role], {})
            return item.get('operstate') == 'UP', any(a.get('family') == 'inet' for a in item.get('addr_info', []))
        eth_link, eth_ip = link('uplink')
        ap_link, ap_ip = link('ap')
        usb_link, usb_ip = link('usb')
        memory = {}
        for line in Path('/proc/meminfo').read_text().splitlines():
            fields = line.split()
            memory[fields[0].rstrip(':')] = int(fields[1]) * 1024
        ruleset = json.loads(self.run(['nft', '-j', 'list', 'table', 'inet', 'phoenix']).stdout)
        counts = {'accept': 0, 'drop': 0}
        for item in ruleset.get('nftables', []):
            rule = item.get('rule', {})
            if rule.get('chain') != 'forward':
                continue
            expr = rule.get('expr', [])
            for verdict in counts:
                if any(verdict in e for e in expr):
                    counts[verdict] += sum(e.get('counter', {}).get('packets', 0) for e in expr if isinstance(e.get('counter', {}), dict))
        return {'uplink': self.uplink_kind, 'uplink_ready': eth_link and eth_ip,
                'ethernet_link': by_name.get(self.ethernet_name, {}).get('operstate') == 'UP',
                'ethernet_ip': any(a.get('family') == 'inet' for a in by_name.get(self.ethernet_name, {}).get('addr_info', [])),
                'wifi_link': eth_link if self.uplink_kind == 'wifi' else False, 'wifi_ip': eth_ip if self.uplink_kind == 'wifi' else False, 'ap_active': ap_link and ap_ip,
                'usb_configured': usb_ip, 'usb_mounted': usb_link, 'usb_suspended': False,
                'vpn_up': self.handshake(), 'direct': self.mode == 'direct',
                'allowed': counts['accept'], 'blocked': counts['drop'], 'malformed': 0,
                'heap_free': memory.get('MemAvailable', 0),
                'uptime_ms': int(float(Path('/proc/uptime').read_text().split()[0]) * 1000),
                'firewall_enforced': self.enforced, 'counter_scope': 'current_nft_ruleset',
                'malformed_counter_available': False}

    def verify_exit(self):
        from ipaddress import IPv4Address
        import re
        if not self.handshake():
            raise NetworkError('vpn_required_for_exit_check')
        result = self.run(['curl', '--interface', 'phwg0', '--noproxy', '*',
                           '--connect-timeout', '5', '--max-time', '12',
                           '--silent', '--show-error', '--fail',
                           'https://1.1.1.1/cdn-cgi/trace'])
        fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        address = str(IPv4Address(fields.get('ip', '')))
        country = fields.get('loc', '')
        if not re.fullmatch('[A-Z]{2}', country):
            raise NetworkError('exit_check_failed')
        return address, country

    def nord_request(self, path, token=None):
        from . import nord, uplink_http
        return nord.get(path, token, transport=lambda path, headers: uplink_http.get(
            path, headers, self.names['uplink'], 0x5048 if self.selected_route else 0))

    def select_uplink(self, policy, name, kind, gateway=None, ap_name=None):
        from ipaddress import IPv4Address, IPv4Interface
        name = interface(name)
        if kind not in ('ethernet', 'wifi'):
            raise ValueError('invalid_uplink')
        candidate = dict(self.names, uplink=name)
        if ap_name:
            candidate['ap'] = interface(ap_name)
        if len(set(candidate.values())) != 4:
            raise ValueError('conflicting_interface_roles')
        self.block(policy)
        addresses = json.loads(self.run(['ip', '-j', 'address', 'show', 'dev', name]).stdout)
        ipv4 = [a for entry in addresses for a in entry.get('addr_info', []) if a.get('family') == 'inet']
        if not ipv4:
            raise NetworkError('uplink_has_no_address')
        address = IPv4Interface(str(ipv4[0]['local']) + '/' + str(ipv4[0]['prefixlen']))
        if gateway is None:
            defaults = json.loads(self.run(['ip', '-j', 'route', 'show', 'default', 'dev', name]).stdout)
            gateway = next((r.get('gateway') for r in defaults if r.get('gateway')), None)
        if gateway is None:
            raise NetworkError('uplink_has_no_gateway')
        gateway = str(IPv4Address(gateway))
        self.run(['ip', 'route', 'flush', 'table', '17710'], optional=True)
        self.run(['ip', 'route', 'add', 'table', '17710', str(address.network), 'dev', name, 'src', str(address.ip)])
        self.run(['ip', 'route', 'add', 'table', '17710', 'default', 'via', gateway, 'dev', name])
        for priority in ('17690', '17710', '17711'):
            self.run(['ip', 'rule', 'del', 'priority', priority], optional=True)
        self.run(['ip', 'rule', 'add', 'priority', '17690', 'fwmark', '0x5048', 'lookup', '17710'])
        for offset, role in enumerate(('ap', 'usb')):
            self.run(['ip', 'rule', 'add', 'priority', str(17710 + offset), 'iif', candidate[role], 'lookup', '17710'])
        self.names, self.uplink_kind, self.selected_route = candidate, kind, True
        self.block(policy)
