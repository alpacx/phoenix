"""Black-box test of the Rust services in disposable Docker containers.

Starts `phoenix control` (root) and `phoenix frontend` (phoenix-web) exactly as
the systemd units do, drives them only through HTTPS, checks real packets
(blocked, direct NAT, ordered deny, inbound forwarding with default deny and
source restriction, WireGuard tunnel with a real handshake, tunnel loss
without direct fallback, disconnect, imported wg-quick profiles: IPv6 parts and
PostUp ignored, PresharedKey, rejection codes, split AllowedIPs without direct
fallback and DNS warning; multiple peers: a failover group whose dead first
member is replaced by a live alternate, and a second site peer used together
with the exit) and reports RSS. With --soak SECONDS it
then cycles connect/loss/reconnect/disconnect/direct through the API and
checks that the worker's RSS and file descriptors stay flat. Never uses host
networking; removes only its own resources.

The gateway needs NET_ADMIN and SYS_ADMIN *inside its own namespaces*: the
latter only to fake /proc/device-tree/model (tmpfs on /sys/firmware) and to
remount /proc/sys writable so the worker can toggle ip_forward.

Usage (repo root): tools/rust-linux.sh build --release &&
    python3 platforms/linux/tests/integration/rust_blackbox.py [--soak SECONDS] [--keep]
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[4]
BINARY = ROOT / 'platforms/linux/rust/target/release/phoenix'
IMAGE = 'phoenix-linux-test:local'
MODEL = 'Phoenix Blackbox Test'
prefix = 'phoenix-rust-' + uuid.uuid4().hex[:8]
networks, containers = [], []


def docker(*args, data=None, check=True, timeout=60):
    return subprocess.run(['docker', *args], input=data, text=True, capture_output=True, check=check, timeout=timeout)


def execute(container, *args, data=None, check=True, timeout=60):
    result = docker('exec', '-i', container, *args, data=data, check=False, timeout=timeout)
    if check and result.returncode:
        raise AssertionError(f'{args}: {result.stderr.strip()}')
    return result


def sh(container, script, check=True):
    return execute(container, 'sh', '-ec', script, check=check)


def reachable(client, url):
    return execute(client, 'curl', '--noproxy', '*', '--connect-timeout', '2', '--max-time', '3', '-fsS', url, check=False).returncode == 0


class Api:
    def __init__(self, gateway, token):
        self.gateway, self.token, self.cookie = gateway, token, ''

    def __call__(self, method, path, body=None, bearer=True, origin=True, expect=None):
        argv = ['curl', '-sk', '--noproxy', '*', '--max-time', '20', '-o', '/dev/stdout', '-w', '\n%{http_code}',
                '-X', method, '-D', '/tmp/headers']
        if bearer:
            argv += ['-H', 'Authorization: Bearer ' + self.token]
        if self.cookie and not bearer:
            argv += ['-H', 'Cookie: __Host-phoenix=' + self.cookie]
        if origin and method == 'POST':
            argv += ['-H', 'Origin: https://127.0.0.1:8443']
        if body is not None:
            argv += ['-H', 'Content-Type: application/json', '--data-binary', '@-']
        result = execute(self.gateway, *argv, 'https://127.0.0.1:8443' + path,
                         data=None if body is None else json.dumps(body))
        text, _, code = result.stdout.rpartition('\n')
        headers = execute(self.gateway, 'cat', '/tmp/headers').stdout
        for line in headers.splitlines():
            if line.lower().startswith('set-cookie: __host-phoenix='):
                self.cookie = line.split('=', 1)[1].split(';', 1)[0]
        value = json.loads(text) if text.strip().startswith(('{', '[')) else text
        if expect is not None and int(code) != expect:
            raise AssertionError(f'{method} {path}: HTTP {code} {value}')
        return int(code), value


def wait_for(predicate, timeout, message):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.5)
    raise AssertionError(message)


def rss(container, role):
    """RSS of the service started by start() (PID recorded at launch)."""
    status = execute(container, 'sh', '-c', f'cat /proc/$(cat /tmp/{role}.pid)/status').stdout
    fields = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
    return {key: int(fields[key].split()[0]) for key in ('VmRSS', 'RssAnon', 'RssFile')}


def prepare_gateway(gateway, names):
    sh(gateway, f'''
mount -o remount,rw /proc/sys
mount -t tmpfs tmpfs /sys/firmware
mkdir -p /sys/firmware/devicetree/base
printf '{MODEL}\\0' > /sys/firmware/devicetree/base/model
id phoenix-web >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin phoenix-web
mkdir -p /opt/phoenix-releases/test/bin /etc/phoenix /var/lib/phoenix /run/phoenix /run/phoenix-control /run/creds
cp /mnt/phoenix /opt/phoenix-releases/test/bin/phoenix && chmod 0755 /opt/phoenix-releases/test/bin/phoenix
chmod 0700 /var/lib/phoenix /etc/phoenix && chgrp phoenix-web /run/phoenix-control && chmod 0750 /run/phoenix-control
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=Phoenix -addext subjectAltName=IP:127.0.0.1 \
  -addext basicConstraints=critical,CA:FALSE -keyout /etc/phoenix/admin-key.pem -out /etc/phoenix/admin-cert.pem 2>/dev/null
''')
    target = {'expected_model': MODEL, 'interfaces': names}
    execute(gateway, 'sh', '-c', 'cat > /etc/phoenix/target.json && chmod 0600 /etc/phoenix/target.json', data=json.dumps(target))


def start(gateway, implementation='rust'):
    """Start worker (root) then frontend (phoenix-web) like the systemd units."""
    if implementation != 'rust':
        raise ValueError('only the Rust services exist')
    sh(gateway, 'rm -rf /var/lib/phoenix/* /run/phoenix-control/* && ip link delete phwg0 2>/dev/null || true')
    worker = '/opt/phoenix-releases/test/bin/phoenix control'
    frontend = '/opt/phoenix-releases/test/bin/phoenix frontend'
    sh(gateway, f'''umask 077
# Group=phoenix-web as in phoenix-control.service: the socket must be group-accessible.
nohup setpriv --regid phoenix-web --clear-groups {worker} --state-dir /var/lib/phoenix --target-config /etc/phoenix/target.json \
  --worker-socket /run/phoenix-control/control.sock >/tmp/worker.log 2>&1 &
echo $! > /tmp/worker.pid
for i in $(seq 1 100); do [ -S /run/phoenix-control/control.sock ] && break; sleep 0.1; done
[ -S /run/phoenix-control/control.sock ] || {{ cat /tmp/worker.log; exit 1; }}
for f in admin-token:/var/lib/phoenix/admin-token tls-key:/etc/phoenix/admin-key.pem tls-cert:/etc/phoenix/admin-cert.pem; do
  install -o phoenix-web -g phoenix-web -m 0400 "${{f#*:}}" "/run/creds/${{f%%:*}}"; done
nohup setpriv --reuid phoenix-web --regid phoenix-web --init-groups {frontend} \
  --token-file /run/creds/admin-token --tls-key /run/creds/tls-key --tls-cert /run/creds/tls-cert >/tmp/frontend.log 2>&1 &
echo $! > /tmp/frontend.pid
for i in $(seq 1 100); do curl -sk -o /dev/null https://127.0.0.1:8443/healthz && break; sleep 0.1; done
''')
    return Api(gateway, execute(gateway, 'cat', '/var/lib/phoenix/admin-token').stdout.strip())


def stop(gateway):
    sh(gateway, '''for role in frontend worker; do
  pid=$(cat /tmp/$role.pid); kill -TERM "$pid" 2>/dev/null || true
  for i in $(seq 1 100); do [ -d /proc/$pid ] || break; sleep 0.1; done
  [ ! -d /proc/$pid ] || { echo "$role did not stop"; exit 1; }
done''')


def wireguard_peer(gateway, peer, psk=None):
    """Fresh WireGuard peer `wgtest` (10.77.0.1) on the peer; returns (profile, gateway private key)."""
    private_peer = execute(peer, 'wg', 'genkey').stdout.strip()
    public_peer = execute(peer, 'wg', 'pubkey', data=private_peer).stdout.strip()
    private_gateway = execute(gateway, 'wg', 'genkey').stdout.strip()
    public_gateway = execute(gateway, 'wg', 'pubkey', data=private_gateway).stdout.strip()
    sh(peer, 'ip link delete wgtest 2>/dev/null || true')
    execute(peer, 'ip', 'link', 'add', 'wgtest', 'type', 'wireguard')
    shared = f'PresharedKey={psk}\n' if psk else ''
    execute(peer, 'wg', 'setconf', 'wgtest', '/dev/stdin', data=f'[Interface]\nPrivateKey={private_peer}\nListenPort=51820\n[Peer]\nPublicKey={public_gateway}\n{shared}AllowedIPs=10.77.0.2/32\n')
    execute(peer, 'ip', 'address', 'add', '10.77.0.1/24', 'dev', 'wgtest')
    execute(peer, 'ip', 'link', 'set', 'wgtest', 'up')
    profile = f'[Interface]\nPrivateKey={private_gateway}\nAddress=10.77.0.2/32\nDNS=10.77.0.1\n[Peer]\nPublicKey={public_peer}\nEndpoint=192.0.2.20:51820\nAllowedIPs=0.0.0.0/0\nPersistentKeepalive=1\n'
    return profile, private_gateway


def vpn_state(api):
    return api('GET', '/api/v1/vpn')[1]['state']


def lose_tunnel(gateway, peer):
    """Tunnel loss with the peer unreachable, so a retry cannot carry traffic either."""
    sh(peer, 'ip link set wgtest down')
    execute(gateway, 'ip', 'link', 'delete', 'phwg0')


def scenario(gateway, client, peer, api, names, full, peer2=None):
    code, health = api('GET', '/healthz', bearer=False)
    assert code == 200 and health['ready'] is True, health
    code, auth = api('GET', '/api/v1/auth/status', bearer=False, expect=200)
    assert auth == {'password_login': True, 'authenticated': False, 'must_change': False}, auth
    api('POST', '/api/v1/auth/login', {'password': 'wrong-password'}, bearer=False, expect=401)
    code, login = api('POST', '/api/v1/auth/login', {'password': 'phoenix'}, bearer=False, expect=200)
    assert login['must_change'] is True and api.cookie
    api('GET', '/api/v1/status', bearer=False, expect=401)
    api('POST', '/api/v1/auth/password', {'current_password': 'phoenix', 'new_password': 'blackbox-pass-1'}, bearer=False, expect=200)
    code, status = api('GET', '/api/v1/status', bearer=False, expect=200)
    assert status['firewall_enforced'] is True and status['direct'] is False, status
    api('GET', '/api/v1/status', bearer=False, origin=False, expect=200)
    api('POST', '/api/v1/vpn', {'action': 'direct'}, bearer=False, origin=False, expect=403)
    print('API: healthz, password login, forced change, session, origin check PASS')
    assert api('GET', '/api/v1/vpn', expect=200)[1]['state'] == 'blocked'
    assert not reachable(client, 'http://192.0.2.20:8000'), 'blocked mode forwarded traffic'
    api('POST', '/api/v1/vpn', {'action': 'direct'}, expect=202)
    wait_for(lambda: api('GET', '/api/v1/vpn')[1]['state'] == 'direct', 10, 'direct mode not reached')
    assert reachable(client, 'http://192.0.2.20:8000'), 'direct NAT failed'
    print('Packets via API: initial block, direct NAT PASS')
    if not full:
        return
    policy = api('GET', '/api/v1/policy', expect=200)[1]
    deny = dict(policy, rules=[{'name': 'Deny HTTP', 'enabled': True, 'allow': False, 'ingress': 'ap', 'protocol': 6,
                                'source': '0.0.0.0/0', 'destination': '0.0.0.0/0', 'port_first': 8000, 'port_last': 8000}])
    saved = api('POST', '/api/v1/policy', deny, expect=200)[1]
    assert saved['revision'] == policy['revision'] + 1, saved
    api('POST', '/api/v1/policy', deny, expect=409)
    assert not reachable(client, 'http://192.0.2.20:8000'), 'ordered deny not enforced'
    allow = dict(saved, rules=[])
    api('POST', '/api/v1/policy', allow, expect=200)
    assert reachable(client, 'http://192.0.2.20:8000'), 'policy revert failed'
    print('Packets via API: policy revision, conflict, ordered deny PASS')
    current = api('GET', '/api/v1/policy', expect=200)[1]
    inbound = {'name': 'Inbound', 'enabled': True, 'vpn': False, 'protocol': 6, 'external_port': 8080,
               'internal_port': 9000, 'target': '192.168.9.20/32', 'source': '192.0.2.20/32'}
    saved = api('POST', '/api/v1/policy', dict(current, default_allow=False, forwards=[inbound]), expect=200)[1]
    assert reachable(peer, 'http://192.0.2.10:8080'), 'port forwarding with default deny failed'
    saved = api('POST', '/api/v1/policy', dict(saved, forwards=[dict(inbound, source='192.0.2.30/32')]), expect=200)[1]
    assert not reachable(peer, 'http://192.0.2.10:8080'), 'port forwarding source restriction failed'
    api('POST', '/api/v1/policy', dict(saved, default_allow=True, forwards=[]), expect=200)
    assert reachable(client, 'http://192.0.2.20:8000'), 'policy revert failed'
    print('Packets via API: inbound forwarding with default deny and source restriction PASS')
    profile, private_gateway = wireguard_peer(gateway, peer)
    api('POST', '/api/v1/vpn', {'action': 'wireguard', 'profile': profile}, expect=202)
    wait_for(lambda: api('GET', '/api/v1/vpn')[1]['state'] == 'connected', 20, 'WireGuard not connected')
    assert reachable(client, 'http://10.77.0.1:8000'), 'tunnel traffic failed'
    vpn = api('GET', '/api/v1/vpn', expect=200)[1]
    assert vpn['provider'] == 'wireguard' and vpn['endpoint'] == '192.0.2.20:51820', vpn
    wait_for(lambda: api('GET', '/api/v1/vpn/history')[1]['entries'], 5, 'history not recorded')
    assert 'PrivateKey' not in json.dumps(vpn) and private_gateway not in json.dumps(api('GET', '/api/v1/status')[1])
    print('Packets via API: WireGuard tunnel, real handshake, history, no key exposure PASS')
    lose_tunnel(gateway, peer)
    wait_for(lambda: vpn_state(api) != 'connected', 10, 'tunnel loss not detected')
    for _ in range(3):
        assert not reachable(client, 'http://192.0.2.20:8000'), 'tunnel loss fell back to direct'
        assert vpn_state(api) != 'direct'
    ruleset = execute(gateway, 'nft', 'list', 'table', 'inet', 'phoenix').stdout
    uplink_nat = [line for line in ruleset.splitlines() if f'oifname "{names["uplink"]}"' in line and 'masquerade' in line]
    assert not uplink_nat, uplink_nat
    sh(peer, 'ip link set wgtest up')
    print('Packets via API: tunnel loss blocks without direct fallback PASS')
    api('POST', '/api/v1/vpn', {'action': 'disconnect'}, expect=202)
    wait_for(lambda: api('GET', '/api/v1/vpn')[1]['state'] == 'blocked', 10, 'disconnect did not block')
    assert not reachable(client, 'http://192.0.2.20:8000'), 'disconnect left forwarding open'
    assert not reachable(client, 'http://10.77.0.1:8000'), 'disconnect left tunnel open'
    print('Packets via API: disconnect blocks without direct fallback PASS')
    imported_profiles(gateway, client, peer, api)
    if peer2:
        multiple_peers(gateway, client, peer, peer2, api)


def imported_profiles(gateway, client, peer, api):
    """Any wg-quick client profile: IPv4 parts used, hooks never executed."""
    psk = execute(peer, 'wg', 'genpsk').stdout.strip()
    _, private_gateway = wireguard_peer(gateway, peer, psk)
    public_peer = execute(peer, 'wg', 'show', 'wgtest', 'public-key').stdout.strip()
    sh(gateway, 'rm -f /tmp/phoenix-postup-marker /tmp/phoenix-postdown-marker')
    full = (f'\ufeff[Interface]\r\n# exported by a wg-quick tool\r\nprivatekey = {private_gateway}\r\n'
            'Address = 10.77.0.2/24, fd77::2/64\r\nAddress = 10.77.0.3/32\r\n'
            'DNS = 10.77.0.1, 9.9.9.9, 2001:db8::53, corp.example\r\nMTU = 1420\r\nListenPort = 51999\r\nTable = off\r\n'
            'PostUp = touch /tmp/phoenix-postup-marker\r\nPostDown = touch /tmp/phoenix-postdown-marker\r\n\r\n'
            f'[peer]\r\nPublicKey = {public_peer}\r\nPresharedKey = {psk}\r\n'
            'AllowedIPs = 0.0.0.0/1, 128.0.0.0/1, ::/0\r\nEndpoint = 192.0.2.20:51820\r\nPersistentKeepalive = 1\r\n')
    accepted = api('POST', '/api/v1/vpn', {'action': 'wireguard', 'profile': full}, expect=202)[1]
    expected = {'ignored_ipv6', 'extra_addresses', 'dns_search_ignored', 'ignored_hooks'}
    assert set(accepted.get('profile_notes', [])) == expected, accepted
    wait_for(lambda: vpn_state(api) == 'connected', 20, 'imported profile not connected')
    assert reachable(client, 'http://10.77.0.1:8000'), 'imported profile: tunnel traffic failed'
    vpn = api('GET', '/api/v1/vpn', expect=200)[1]
    assert set(vpn['profile_notes']) == expected and psk not in json.dumps(vpn), vpn
    assert execute(gateway, 'wg', 'show', 'phwg0', 'preshared-keys').stdout.split()[-1] != '(none)', 'PresharedKey not applied'
    assert execute(gateway, 'wg', 'show', 'phwg0', 'listen-port').stdout.strip() != '51999', 'ListenPort must be ignored'
    assert 'mtu 1420' in execute(gateway, 'ip', 'link', 'show', 'phwg0').stdout
    other = execute(peer, 'wg', 'pubkey', data=execute(peer, 'wg', 'genkey').stdout).stdout.strip()
    overlap = f'[Peer]\r\nPublicKey = {other}\r\nEndpoint = 192.0.2.21:51820\r\nAllowedIPs = 0.0.0.0/1, 10.0.0.0/8\r\n[peer]'
    for bad, code in [(full.replace('[peer]', overlap), 'allowed_ips_partial_overlap'),
                      (full.replace('192.0.2.20:51820', '[2001:db8::1]:51820'), 'ipv6_endpoint_unsupported'),
                      (full.replace('MTU = 1420', 'MTU = 9000'), 'invalid_number')]:
        assert api('POST', '/api/v1/vpn', {'action': 'wireguard', 'profile': bad}, expect=400)[1] == {'error': code}
    assert vpn_state(api) == 'connected', 'a rejected import must not touch the active tunnel'
    print('Imported profile: BOM/CRLF/mixed case, IPv6 and DNS search ignored, PresharedKey, MTU, rejection codes PASS')
    split = (f'[Interface]\nPrivateKey = {private_gateway}\nAddress = 10.77.0.2/32\n[Peer]\nPublicKey = {public_peer}\n'
             f'PresharedKey = {psk}\nAllowedIPs = 10.77.0.0/24\nEndpoint = 192.0.2.20:51820\nPersistentKeepalive = 1\n')
    accepted = api('POST', '/api/v1/vpn', {'action': 'wireguard', 'profile': split}, expect=202)[1]
    assert set(accepted['profile_notes']) == {'split_allowed_ips', 'dns_fallback', 'dns_outside_allowed_ips'}, accepted
    assert accepted['profile_details'] == {'dns_outside_allowed_ips': ['1.1.1.1']}, accepted
    wait_for(lambda: vpn_state(api) == 'connected', 20, 'split profile not connected')
    assert reachable(client, 'http://10.77.0.1:8000'), 'split profile: in-range traffic failed'
    for _ in range(2):
        assert not reachable(client, 'http://192.0.2.20:8000'), 'split profile leaked out-of-range traffic outside the tunnel'
    print('Imported profile: split AllowedIPs, in-range through the tunnel, rest blocked (no direct fallback), DNS warning PASS')
    api('POST', '/api/v1/vpn', {'action': 'disconnect'}, expect=202)
    wait_for(lambda: vpn_state(api) == 'blocked', 10, 'disconnect did not block')
    sh(gateway, 'test ! -e /tmp/phoenix-postup-marker && test ! -e /tmp/phoenix-postdown-marker')
    print('Imported profile: PostUp/PostDown never executed PASS')


def wireguard_site(gateway, peer2, private_gateway):
    """Second WireGuard server `wgtest2` (10.88.0.1/24, port 51821) on peer2 for the same gateway key."""
    public_gateway = execute(gateway, 'wg', 'pubkey', data=private_gateway).stdout.strip()
    private_site = execute(peer2, 'wg', 'genkey').stdout.strip()
    sh(peer2, 'ip link delete wgtest2 2>/dev/null || true')
    execute(peer2, 'ip', 'link', 'add', 'wgtest2', 'type', 'wireguard')
    execute(peer2, 'wg', 'setconf', 'wgtest2', '/dev/stdin', data=f'[Interface]\nPrivateKey={private_site}\nListenPort=51821\n[Peer]\nPublicKey={public_gateway}\nAllowedIPs=10.77.0.2/32\n')
    execute(peer2, 'ip', 'address', 'add', '10.88.0.1/24', 'dev', 'wgtest2')
    execute(peer2, 'ip', 'link', 'set', 'wgtest2', 'up')
    execute(peer2, 'ip', 'route', 'replace', '10.77.0.2/32', 'dev', 'wgtest2')
    return execute(peer2, 'wg', 'pubkey', data=private_site).stdout.strip()


def multiple_peers(gateway, client, peer, peer2, api):
    """Failover group (identical AllowedIPs, one member at a time) and a site
    peer with its own AllowedIPs used together with the exit."""
    _, private_gateway = wireguard_peer(gateway, peer)
    public_peer = execute(peer, 'wg', 'show', 'wgtest', 'public-key').stdout.strip()
    dead = execute(peer, 'wg', 'pubkey', data=execute(peer, 'wg', 'genkey').stdout).stdout.strip()
    interface = f'[Interface]\nPrivateKey = {private_gateway}\nAddress = 10.77.0.2/32\nDNS = 10.77.0.1\n'
    live = f'[Peer]\nPublicKey = {public_peer}\nEndpoint = 192.0.2.20:51820\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = 1\n'
    # Nothing listens on 51999: the first member never completes a handshake.
    failover = interface + f'[Peer]\nPublicKey = {dead}\nEndpoint = 192.0.2.20:51999\nAllowedIPs = 0.0.0.0/0, ::/0\nPersistentKeepalive = 1\n' + live
    started = time.monotonic()
    accepted = api('POST', '/api/v1/vpn', {'action': 'wireguard', 'profile': failover}, expect=202)[1]
    assert set(accepted['profile_notes']) == {'ignored_ipv6', 'multiple_peers'}, accepted
    assert accepted['profile_details'] == {'multiple_peers': {'peers': 2, 'groups': 1}}, accepted
    wait_for(lambda: vpn_state(api) == 'connecting', 10, 'failover profile not started')
    peers = api('GET', '/api/v1/vpn')[1]['peers']
    assert [(p['endpoint'], p['active'], p['connected']) for p in peers] == [('192.0.2.20:51999', True, False), ('192.0.2.20:51820', False, False)], peers
    assert private_gateway not in json.dumps(peers)
    def dead_in_use():
        return api('GET', '/api/v1/vpn')[1]['peers'][0]['active']
    deadline, probes = time.monotonic() + 60, 0
    while vpn_state(api) != 'connected':
        assert time.monotonic() < deadline, 'failover did not reach the live alternate'
        # 192.0.2.20 is also reachable through the live tunnel: only probe
        # while the dead member is in use before and after the request.
        if dead_in_use():
            leaked = reachable(client, 'http://192.0.2.20:8000')
            if dead_in_use():
                assert not leaked, 'traffic left the gateway while the exit member was dead'
                probes += 1
        time.sleep(1)
    assert probes >= 3, probes
    elapsed = time.monotonic() - started
    assert 30 <= elapsed <= 50, f'failover after {elapsed:.0f} s'
    assert reachable(client, 'http://10.77.0.1:8000'), 'failover: tunnel traffic failed'
    vpn = api('GET', '/api/v1/vpn', expect=200)[1]
    assert vpn['endpoint'] == '192.0.2.20:51820', vpn
    assert [(p['active'], p['connected']) for p in vpn['peers']] == [(False, False), (True, True)], vpn['peers']
    assert execute(gateway, 'wg', 'show', 'phwg0', 'peers').stdout.split() == [public_peer], 'alternates never coexist in wg'
    print(f'Multiple peers: dead exit member replaced by the live alternate after {elapsed:.0f} s, never direct PASS')

    public_site = wireguard_site(gateway, peer2, private_gateway)
    together = interface + live + f'[Peer]\nPublicKey = {public_site}\nEndpoint = 192.0.2.21:51821\nAllowedIPs = 10.88.0.0/24\nPersistentKeepalive = 1\n'
    accepted = api('POST', '/api/v1/vpn', {'action': 'wireguard', 'profile': together}, expect=202)[1]
    assert accepted['profile_details'] == {'multiple_peers': {'peers': 2, 'groups': 2}}, accepted
    wait_for(lambda: vpn_state(api) == 'connected', 20, 'two-group profile not connected')
    wait_for(lambda: all(p['connected'] for p in api('GET', '/api/v1/vpn')[1]['peers']), 20, 'site peer without handshake')
    assert reachable(client, 'http://10.77.0.1:8000'), 'exit peer traffic failed'
    assert reachable(client, 'http://10.88.0.1:8000'), 'site peer traffic failed'
    assert sorted(execute(gateway, 'wg', 'show', 'phwg0', 'peers').stdout.split()) == sorted([public_peer, public_site])
    print('Multiple peers: exit 0.0.0.0/0 and site 10.88.0.0/24 used together PASS')
    api('POST', '/api/v1/vpn', {'action': 'disconnect'}, expect=202)
    wait_for(lambda: vpn_state(api) == 'blocked', 10, 'disconnect did not block')
    assert not reachable(client, 'http://10.88.0.1:8000'), 'disconnect left the site tunnel open'


def soak(gateway, client, peer, api, seconds):
    """Cycle the VPN state machine via the API; worker RSS/fds must stay flat."""
    profile, _ = wireguard_peer(gateway, peer)
    samples = []

    def sample(action):
        status = rss(gateway, 'worker')
        fds = int(execute(gateway, 'sh', '-c', 'ls /proc/$(cat /tmp/worker.pid)/fd | wc -l').stdout)
        samples.append({'action': action, 'rss_kib': status['VmRSS'], 'fds': fds})

    def request(action, state, body=None):
        api('POST', '/api/v1/vpn', dict(body or {}, action=action), expect=202)
        wait_for(lambda: vpn_state(api) == state, 20, f'soak: {action} did not reach {state}')

    started, cycles = time.monotonic(), 0
    while time.monotonic() - started < seconds:
        request('wireguard', 'connected', {'profile': profile})
        assert reachable(client, 'http://10.77.0.1:8000'), 'soak: tunnel traffic failed'
        sample('connect')
        lose_tunnel(gateway, peer)
        wait_for(lambda: vpn_state(api) != 'connected', 10, 'soak: loss not detected')
        assert not reachable(client, 'http://192.0.2.20:8000'), 'soak: loss fell back to direct'
        sample('loss')
        sh(peer, 'ip link set wgtest up')
        request('wireguard', 'connected', {'profile': profile})
        assert reachable(client, 'http://10.77.0.1:8000'), 'soak: reconnect failed'
        sample('reconnect')
        request('disconnect', 'blocked')
        assert not reachable(client, 'http://192.0.2.20:8000'), 'soak: disconnect left forwarding open'
        sample('disconnect')
        request('direct', 'direct')
        assert reachable(client, 'http://192.0.2.20:8000'), 'soak: direct NAT failed'
        sample('direct')
        request('disconnect', 'blocked')
        sample('disconnect')
        cycles += 1
        if cycles % 5 == 0:
            print(json.dumps({'soak_cycles': cycles, 'elapsed_seconds': round(time.monotonic() - started),
                              'rss_kib': samples[-1]['rss_kib'], 'fds': samples[-1]['fds']}), flush=True)
    warm = samples[len(samples) // 3:] if len(samples) >= 6 else samples
    report = {'elapsed_seconds': round(time.monotonic() - started), 'cycles': cycles, 'samples': len(samples),
              'rss_first_kib': samples[0]['rss_kib'],
              'rss_min_kib': min(x['rss_kib'] for x in warm), 'rss_max_kib': max(x['rss_kib'] for x in warm),
              'fds_min': min(x['fds'] for x in warm), 'fds_max': max(x['fds'] for x in warm)}
    assert report['rss_max_kib'] - report['rss_min_kib'] < 2048, report
    assert report['fds_max'] - report['fds_min'] <= 2, report
    print('SOAK PASS ' + json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--soak', type=int, default=0, metavar='SECONDS', help='30..1200 seconds of API cycles')
    parser.add_argument('--keep', action='store_true', help='keep containers and networks for debugging')
    options = parser.parse_args()
    if options.soak and not 30 <= options.soak <= 1200:
        parser.error('--soak must be 30..1200 seconds')
    if not BINARY.exists():
        raise SystemExit('Build first: tools/rust-linux.sh build --release')
    if docker('image', 'inspect', IMAGE, check=False).returncode:
        docker('build', '-q', '-t', IMAGE, str(ROOT / 'platforms/linux/tests/integration'), timeout=900)
    try:
        for suffix, subnet in [('lan', '192.168.9.0/24'), ('wan', '192.0.2.0/24')]:
            name = prefix + '-' + suffix
            docker('network', 'create', '--opt', 'com.docker.network.bridge.enable_ip_masquerade=false', '--subnet', subnet, name)
            networks.append(name)
        gateway, client, peer, peer2 = [prefix + '-' + n for n in ('gateway', 'client', 'peer', 'peer2')]
        for name, network, ip, extra in [
                (gateway, networks[1], '192.0.2.10', ['--cap-add', 'SYS_ADMIN', '--security-opt', 'apparmor=unconfined',
                                                      '--mount', f'type=bind,source={BINARY},target=/mnt/phoenix,readonly']),
                (client, networks[0], '192.168.9.20', []),
                (peer, networks[1], '192.0.2.20', []),
                (peer2, networks[1], '192.0.2.21', [])]:
            docker('run', '-d', '--init', '--name', name, '--cap-add', 'NET_ADMIN',
                   '--sysctl', 'net.ipv4.conf.all.rp_filter=0', '--sysctl', 'net.ipv4.conf.default.rp_filter=0',
                   '--network', network, '--ip', ip, *extra,
                   '--mount', f'type=bind,source={ROOT},target=/workspace,readonly', IMAGE, 'sleep', '1800')
            containers.append(name)
        docker('network', 'connect', '--ip', '192.168.9.10', networks[0], gateway)
        execute(client, 'ip', 'route', 'replace', 'default', 'via', '192.168.9.10')
        execute(gateway, 'ip', 'link', 'add', 'usbtest', 'type', 'dummy')
        docker('exec', '-d', peer, 'python3', '-m', 'http.server', '8000', '--bind', '0.0.0.0')
        docker('exec', '-d', peer2, 'python3', '-m', 'http.server', '8000', '--bind', '0.0.0.0')
        docker('exec', '-d', client, 'python3', '-m', 'http.server', '9000', '--bind', '0.0.0.0')
        links = json.loads(execute(gateway, 'ip', '-j', 'address', 'show').stdout)
        def by_ip(address):
            return next(l['ifname'] for l in links if any(a.get('local') == address for a in l.get('addr_info', [])))
        names = {'ap': by_ip('192.168.9.10'), 'uplink': by_ip('192.0.2.10'), 'usb': 'usbtest', 'vpn': 'phwg0'}
        prepare_gateway(gateway, names)
        api = start(gateway, 'rust')
        try:
            scenario(gateway, client, peer, api, names, full=True, peer2=peer2)
            time.sleep(2)
            report = {'worker_kib': rss(gateway, 'worker'), 'frontend_kib': rss(gateway, 'frontend')}
            if options.soak:
                soak(gateway, client, peer, api, options.soak)
        except BaseException:
            print('--- worker log ---\n' + execute(gateway, 'cat', '/tmp/worker.log', check=False).stdout[-4000:])
            print('--- frontend log ---\n' + execute(gateway, 'cat', '/tmp/frontend.log', check=False).stdout[-4000:])
            raise
        stop(gateway)
        assert execute(gateway, 'cat', '/proc/sys/net/ipv4/ip_forward').stdout.strip() == '0', 'forwarding left on after stop'
        execute(gateway, '/opt/phoenix-releases/test/bin/phoenix', 'stop-guard')
        assert 'phoenix_stop' in execute(gateway, 'nft', 'list', 'tables').stdout
        execute(gateway, 'nft', 'delete', 'table', 'inet', 'phoenix_stop')
        sh(gateway, 'echo 0 > /proc/sys/net/ipv4/ip_forward')
        print('Shutdown: forwarding off, stop guard table installed PASS')
        print('RSS (KiB, after scenario): ' + json.dumps(report))
        print('RUST BLACKBOX PASS')
    finally:
        if options.keep:
            print('Kept for debugging: ' + ' '.join(containers + networks))
        else:
            for name in reversed(containers):
                docker('rm', '-f', name, check=False)
            for name in reversed(networks):
                docker('network', 'rm', name, check=False)


if __name__ == '__main__':
    main()
