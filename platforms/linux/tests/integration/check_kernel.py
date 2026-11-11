"""Runs exclusively inside an isolated Linux container with NET_ADMIN."""
import json
import subprocess
from pathlib import Path
from phoenix_linux.firewall import compile_rules
from phoenix_linux.runtime import Runtime, Runner
from phoenix_linux.wireguard import parse


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)

if not Path('/.dockerenv').exists():
    raise SystemExit('This test must run inside Docker, never on the target or host')

policy = {'revision': 0, 'default_allow': True, 'rules': [
    {'name': 'Deny HTTPS', 'enabled': True, 'allow': False, 'ingress': 'ap',
     'protocol': 6, 'source': '192.168.9.0/24', 'destination': '0.0.0.0/0', 'port_first': 443, 'port_last': 443}],
    'forwards': [{'name': 'Test', 'enabled': True, 'vpn': False, 'protocol': 6,
                  'external_port': 8080, 'internal_port': 80, 'target': '192.168.9.2/32', 'source': '0.0.0.0/0'}]}
names = {'ap': 'aptest', 'usb': 'usbtest', 'uplink': 'eth0', 'vpn': 'phwg0'}
for name in ('aptest', 'usbtest'):
    run('ip', 'link', 'add', name, 'type', 'dummy')
    run('ip', 'link', 'set', name, 'up')
for mode in ('blocked', 'direct', 'vpn'):
    script = compile_rules(policy, names, mode, existing=mode != 'blocked')
    subprocess.run(['nft', '--check', '-f', '-'], input=script, text=True, check=True)
    subprocess.run(['nft', '-f', '-'], input=script, text=True, check=True)
print('nftables: blocked/direct/vpn parsed and installed in isolated namespace')
runner = Runner()
runtime = Runtime(names, runner)
runtime.block(policy)
private = run('wg', 'genkey').stdout.strip()
public = subprocess.run(['wg', 'pubkey'], input=private, text=True, capture_output=True, check=True).stdout.strip()
profile = parse(f'[Interface]\nPrivateKey={private}\nAddress=10.77.0.2/32\nDNS=1.1.1.1\n[Peer]\nPublicKey={public}\nEndpoint=192.0.2.1:51820\nAllowedIPs=0.0.0.0/0\n')
runtime.connect(policy, profile)
assert not runtime.handshake(), 'No real peer exists in this test'
assert runtime.status()['firewall_enforced']
runtime.direct(policy)
assert runtime.mode == 'direct'
runtime.block(policy)
print('WireGuard interface, setconf, policy routes, status, direct and block transitions PASS')
print('No external VPN handshake or hardware throughput claimed')
