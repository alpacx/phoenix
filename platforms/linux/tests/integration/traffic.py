"""Isolated Docker packet tests. Never uses host networking or privileged mode.

Creates two dedicated networks with Docker masquerading disabled and three disposable containers; removes only
resources created by this run. Requires the phoenix-linux-test:local image.
"""
import json
import os
import select
from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[4]
IMAGE = 'phoenix-linux-test:local'
prefix = 'phoenix-test-' + uuid.uuid4().hex[:10]
networks, containers = [], []


def docker(*args, data=None, check=True):
    return subprocess.run(['docker', *args], input=data, text=True, capture_output=True, check=check, timeout=45)


def execute(container, *args, data=None, check=True):
    return docker('exec', '-i', container, *args, data=data, check=check)


def python(container, script):
    result = execute(container, 'python3', '-', data=script, check=False)
    if result.returncode:
        raise RuntimeError('Container check failed: ' + result.stderr)
    return result


def request(address, expected):
    result = execute(client, 'curl', '--noproxy', '*', '--connect-timeout', '2', '--max-time', '3', '-fsS', address, check=False)
    success = result.returncode == 0
    if success != expected:
        raise AssertionError(f'Unexpected connectivity {address}: success={success}; curl={result.stderr}; gateway_routes={execute(gateway, "ip", "route").stdout}; client_routes={execute(client, "ip", "route").stdout}; rules={execute(gateway, "nft", "list", "ruleset").stdout}; listeners={execute(peer, "ss", "-lnt").stdout}')

try:
    for suffix, subnet in [('lan', '192.168.9.0/24'), ('wan', '192.0.2.0/24')]:
        name = prefix + '-' + suffix
        docker('network', 'create', '--opt', 'com.docker.network.bridge.enable_ip_masquerade=false', '--subnet', subnet, name)
        networks.append(name)
    gateway, client, peer = [prefix + '-' + name for name in ('gateway', 'client', 'peer')]
    for name, network, ip in [(gateway, networks[1], '192.0.2.10'),
                               (client, networks[0], '192.168.9.20'),
                               (peer, networks[1], '192.0.2.20')]:
        docker('run', '-d', '--name', name, '--cap-add', 'NET_ADMIN',
               '--sysctl', 'net.ipv4.ip_forward=1',
               '--sysctl', 'net.ipv4.conf.all.rp_filter=0',
               '--sysctl', 'net.ipv4.conf.default.rp_filter=0',
               '--network', network, '--ip', ip,
               '--mount', f'type=bind,source={ROOT},target=/workspace,readonly',
               IMAGE, 'sleep', '1800')
        containers.append(name)
    docker('network', 'connect', '--ip', '192.168.9.10', networks[0], gateway)
    execute(client, 'ip', 'route', 'replace', 'default', 'via', '192.168.9.10')
    execute(gateway, 'ip', 'link', 'add', 'usbtest', 'type', 'dummy')
    # IP forwarding is confined to this container namespace.
    python(gateway, "from pathlib import Path; assert Path('/proc/sys/net/ipv4/ip_forward').read_text().strip() == '1'")
    docker('exec', '-d', peer, 'python3', '-m', 'http.server', '8000', '--bind', '0.0.0.0')
    links = json.loads(execute(gateway, 'ip', '-j', 'address', 'show').stdout)
    def by_ip(address):
        return next(link['ifname'] for link in links if any(a.get('local') == address for a in link.get('addr_info', [])))
    names = {'ap': by_ip('192.168.9.10'), 'uplink': by_ip('192.0.2.10'), 'usb': 'usbtest', 'vpn': 'phwg0'}
    policy = {'revision': 0, 'default_allow': True, 'rules': [], 'forwards': []}
    def apply(mode, policy=policy):
        python(gateway, f'''from phoenix_linux.runtime import Runtime, Runner
r=Runtime({names!r},Runner())
r.block({policy!r})
r.firewall({policy!r}, {mode!r})
''')
    time.sleep(0.5)
    apply('blocked')
    request('http://192.0.2.20:8000', False)
    apply('direct')
    request('http://192.0.2.20:8000', True)
    denied = dict(policy, rules=[dict(name='Deny HTTP', enabled=True, allow=False, ingress='ap', protocol=6,
                  source='0.0.0.0/0', destination='0.0.0.0/0', port_first=8000, port_last=8000)])
    apply('direct', denied)
    request('http://192.0.2.20:8000', False)
    print('Packets: initial block, direct NAT and ordered deny PASS')
    docker('exec', '-d', client, 'python3', '-m', 'http.server', '9000', '--bind', '0.0.0.0')
    forwarded = dict(policy, default_allow=False, forwards=[dict(name='Inbound', enabled=True,
        vpn=False, protocol=6, external_port=8080, internal_port=9000,
        target='192.168.9.20/32', source='192.0.2.20/32')])
    apply('direct', forwarded)
    time.sleep(0.3)
    response = execute(peer, 'curl', '--noproxy', '*', '--max-time', '3', '-fsS', 'http://192.0.2.10:8080', check=False)
    assert response.returncode == 0, 'Port forwarding with default deny failed'
    forwarded['forwards'][0]['source'] = '192.0.2.30/32'
    apply('direct', forwarded)
    response = execute(peer, 'curl', '--noproxy', '*', '--max-time', '2', '-fsS', 'http://192.0.2.10:8080', check=False)
    assert response.returncode != 0, 'Port forwarding source restriction failed'
    print('Packets: inbound forwarding with default deny and source restriction PASS')
    private_peer = execute(peer, 'wg', 'genkey').stdout.strip()
    public_peer = execute(peer, 'wg', 'pubkey', data=private_peer).stdout.strip()
    private_gateway = execute(gateway, 'wg', 'genkey').stdout.strip()
    public_gateway = execute(gateway, 'wg', 'pubkey', data=private_gateway).stdout.strip()
    execute(peer, 'ip', 'link', 'add', 'wgtest', 'type', 'wireguard')
    execute(peer, 'wg', 'setconf', 'wgtest', '/dev/stdin', data=f'[Interface]\nPrivateKey={private_peer}\nListenPort=51820\n[Peer]\nPublicKey={public_gateway}\nAllowedIPs=10.77.0.2/32\n')
    execute(peer, 'ip', 'address', 'add', '10.77.0.1/24', 'dev', 'wgtest')
    execute(peer, 'ip', 'link', 'set', 'wgtest', 'up')
    profile = f'[Interface]\nPrivateKey={private_gateway}\nAddress=10.77.0.2/32\nDNS=10.77.0.1\n[Peer]\nPublicKey={public_peer}\nEndpoint=192.0.2.20:51820\nAllowedIPs=0.0.0.0/0\nPersistentKeepalive=1\n'
    python(gateway, f'''from phoenix_linux.runtime import Runtime, Runner
from phoenix_linux.wireguard import parse
r=Runtime({names!r},Runner())
r.select_uplink({policy!r}, {names['uplink']!r}, 'ethernet', gateway='192.0.2.1')
r.connect({policy!r},parse({profile!r}))
''')
    time.sleep(1)
    request('http://10.77.0.1:8000', True)
    handshake = execute(gateway, 'wg', 'show', 'phwg0', 'latest-handshakes').stdout.split()
    assert int(handshake[1]) > 0
    execute(gateway, 'ip', 'link', 'delete', 'phwg0')
    request('http://192.0.2.20:8000', False)
    print('Packets: WireGuard tunnel + real handshake + tunnel-loss no direct fallback PASS')
    duration = int(os.environ.get('PHOENIX_SOAK_SECONDS', '0'))
    if duration:
        if not 30 <= duration <= 1200:
            raise ValueError('Soak duration must be 30..1200 seconds')
        worker=subprocess.Popen(['docker','exec','-i',gateway,'python3','platforms/linux/tests/integration/soak_worker.py'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        samples=[]
        def control(action):
            worker.stdin.write(json.dumps({'action':action})+'\n');worker.stdin.flush()
            if not select.select([worker.stdout],[],[],20)[0]:
                raise AssertionError('Persistent worker timeout')
            result=json.loads(worker.stdout.readline())
            assert 'error' not in result, result
            samples.append(result)
            return result
        started=time.monotonic()
        cycles=0
        try:
            worker.stdin.write(json.dumps({'names':names,'profile':profile})+'\n');worker.stdin.flush()
            while time.monotonic()-started < duration:
                assert control('connect')['mode']=='vpn'
                request('http://10.77.0.1:8000',True)
                assert control('loss')['mode']=='blocked'
                request('http://192.0.2.20:8000',False)
                assert control('connect')['mode']=='vpn'
                request('http://10.77.0.1:8000',True)
                assert control('disconnect')['mode']=='blocked'
                request('http://192.0.2.20:8000',False)
                assert control('direct')['mode']=='direct'
                request('http://192.0.2.20:8000',True)
                control('disconnect')
                cycles+=1
                if cycles%5==0:
                    print(json.dumps({'soak_cycles':cycles,'elapsed_seconds':round(time.monotonic()-started),'rss_kib':samples[-1]['rss_kib'],'fds':samples[-1]['fds']}),flush=True)
            warm=samples[min(30,len(samples)-1):]
            report={'elapsed_seconds':round(time.monotonic()-started),'cycles':cycles,
                    'rss_min_kib':min(x['rss_kib'] for x in warm),'rss_max_kib':max(x['rss_kib'] for x in warm),
                    'fds_min':min(x['fds'] for x in warm),'fds_max':max(x['fds'] for x in warm)}
            assert report['rss_max_kib']-report['rss_min_kib']<8192, report
            assert report['fds_max']-report['fds_min']<=2, report
            print('SOAK PASS '+json.dumps(report),flush=True)
        finally:
            worker.stdin.close()
            worker.wait(timeout=20)
    # Fixture source 1.1.1.1 has a deliberately blackholed main reverse route.
    # Disable host-inherited reverse-path filtering only in test namespaces;
    # otherwise Linux can discard the reply before the socket sees it.
    # Real bound TCP/TLS and DoH fixture: main route deliberately cannot reach DNS.
    execute(peer, 'ip', 'address', 'add', '1.1.1.1/32', 'dev', 'lo')
    execute(peer, 'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
        '-subj', '/CN=Local uplink test', '-addext', 'subjectAltName=IP:1.1.1.1,DNS:api.nordvpn.com',
        '-keyout', '/tmp/fixture-key.pem', '-out', '/tmp/fixture-cert.pem')
    certificate = execute(peer, 'cat', '/tmp/fixture-cert.pem').stdout
    python(gateway, f"from pathlib import Path; Path('/tmp/fixture-ca.pem').write_text({certificate!r})")
    docker('exec', '-d', peer, 'python3', 'platforms/linux/tests/integration/https_fixture.py')
    execute(gateway, 'ip', 'route', 'add', 'blackhole', '1.1.1.1/32')
    time.sleep(0.5)
    python(gateway, f'''from phoenix_linux.runtime import Runtime, Runner
from phoenix_linux import uplink_http
from unittest.mock import patch
import ssl
r=Runtime({names!r},Runner())
r.select_uplink({policy!r}, {names['uplink']!r}, 'ethernet', gateway='192.0.2.20')
context=ssl.create_default_context(cafile='/tmp/fixture-ca.pem')
with patch.object(uplink_http.ssl, 'create_default_context', return_value=context):
    assert r.nord_request('/v1/fixture') == {{'local_fixture':True}}
    r.run(['ip','link','set',r.names['uplink'],'down'])
    try:
        r.nord_request('/v1/fixture')
    except ValueError:
        pass
    else:
        raise AssertionError('Provisioning used an alternate interface after link loss')
''')
    print('Packets: real TLS + DoH fixture on selected uplink despite main-route blackhole; no fallback after link loss PASS')
finally:
    for name in reversed(containers):
        docker('rm', '-f', name, check=False)
    for name in reversed(networks):
        docker('network', 'rm', name, check=False)
