"""Run only inside the disposable QEMU guest. Never execute on a real target.

Drives the Rust `phoenix` binary (/opt/source/phoenix) and the systemd units
from platforms/linux/deploy through install, HTTPS API, signed updates,
rollback and a real reboot. Python here is only the test driver (stdlib).
"""
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

PHOENIX = '/opt/source/phoenix'
DEPLOY = '/opt/source/deploy'
STATE = Path('/var/lib/phoenix/update-state.json')


def run(*args, timeout=90):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout).stdout


def wait(predicate, seconds=100):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            if predicate():
                return
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError('VM condition timeout')


def state():
    return json.loads(STATE.read_text())


def write_state(value):
    """Same on-disk form as the Rust vault: private JSON replaced atomically."""
    temporary = STATE.with_name('.vm-state.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write(json.dumps(value))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, STATE)


def opener():
    context = ssl.create_default_context(cafile='/etc/phoenix/admin-cert.pem')
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))


def healthz():
    with opener().open('https://127.0.0.1:8443/healthz', timeout=5) as response:
        return json.loads(response.read())


def rss_kib(unit):
    pid = run('systemctl', 'show', unit, '-p', 'MainPID', '--value').strip()
    status = Path('/proc/' + pid + '/status').read_text()
    return int(next(line for line in status.splitlines() if line.startswith('VmRSS:')).split()[1])


try:
    model = Path('/proc/device-tree/model').read_text().strip('\0\n')
    if 'dummy-virt' not in model and 'QEMU' not in model:
        raise RuntimeError('Not the isolated QEMU target')
    for name in ('testwan', 'testap', 'testusb'):
        run('ip', 'link', 'add', name, 'type', 'dummy')
        run('ip', 'link', 'set', name, 'up')
    run('ip', 'address', 'add', '192.0.2.10/24', 'dev', 'testwan')
    run('ip', 'route', 'add', 'default', 'via', '192.0.2.1', 'dev', 'testwan')
    marker = Path('/opt/vm/reboot-check')
    if marker.exists():
        run('systemctl', 'start', 'phoenix.service', timeout=180)
        wait(lambda: healthz()['ready'])
        recovered = state()
        assert recovered['phase'] == 'rolled_back' and recovered['error'] == 'interrupted_update', recovered
        assert Path('/opt/phoenix').resolve().name == marker.read_text()
        assert healthz()['release_id'] == marker.read_text()
        assert recovered['max_sequence'] == 6, recovered
        print('VM ALL CHECKS PASS: actual reboot recovered interrupted update before starting services', flush=True)
        run('systemctl', 'poweroff')
        sys.exit(0)

    key, pub = '/opt/vm/private.pem', '/opt/vm/public.pem'
    run('openssl', 'genpkey', '-algorithm', 'ED25519', '-out', key)
    Path(key).chmod(0o600)
    run('openssl', 'pkey', '-in', key, '-pubout', '-out', pub)
    config = Path('/opt/vm/target.json')
    config.write_text(json.dumps({'expected_model': model, 'interfaces': {'ap': 'testap', 'usb': 'testusb', 'uplink': 'testwan', 'vpn': 'phwg0'}}))
    run(PHOENIX, 'package', 'build', '/opt/vm/factory.zip', '--binary', PHOENIX, '--deploy-dir', DEPLOY)
    run(PHOENIX, 'package', 'verify', '/opt/vm/factory.zip')
    # install creates the phoenix-web system user itself.
    run(PHOENIX, 'install', '--bundle', '/opt/vm/factory.zip', '--target-config', str(config), '--public-key', pub, timeout=300)
    assert Path('/opt/phoenix').resolve().name == 'factory'
    assert Path('/opt/phoenix-bootstrap/bin/phoenix').read_bytes() == Path(PHOENIX).read_bytes()
    run('systemctl', 'mask', 'systemd-networkd-wait-online.service', 'NetworkManager-wait-online.service')
    run('systemctl', 'daemon-reload')
    run('systemctl', 'start', 'phoenix.service', timeout=180)
    token = Path('/var/lib/phoenix/admin-token').read_text().strip()

    def request(path, body=None, binary=False, headers=None):
        headers = {'Authorization': 'Bearer ' + token} if headers is None else dict(headers)
        if body is not None:
            headers['Content-Type'] = 'application/octet-stream' if binary else 'application/json'
            if not binary:
                body = json.dumps(body).encode()
        with opener().open(urllib.request.Request('https://127.0.0.1:8443/' + path, data=body, headers=headers), timeout=30) as response:
            return json.loads(response.read())

    def upload(path):
        try:
            request('api/v1/firmware', Path(path).read_bytes(), True)
        except urllib.error.HTTPError as error:
            raise AssertionError(f'upload rejected: HTTP {error.code} {error.read()[:200]!r}')
        except OSError:
            pass  # The service may stop before the accepted response reaches the client.

    wait(lambda: healthz()['ready'])
    assert healthz()['release_id'] == 'factory'
    frontend = run('systemctl', 'show', 'phoenix.service', '-p', 'MainPID', '--value').strip()
    proc = Path('/proc/' + frontend + '/status').read_text()
    assert 'Uid:\t0\t' not in proc and 'CapEff:\t0000000000000000' in proc
    assert request('api/v1/status')['direct'] is False
    assert Path('/proc/sys/net/ipv4/ip_forward').read_text().strip() == '1'
    print('VM PASS: Rust install, systemd boot, unprivileged HTTPS, trusted CA:FALSE certificate, root worker and blocked initial network', flush=True)
    print('VM RSS KiB: ' + json.dumps({'phoenix-control': rss_kib('phoenix-control.service'), 'phoenix': rss_kib('phoenix.service')}), flush=True)
    denied = subprocess.run(['runuser', '-u', 'phoenix-web', '--', 'cat', '/var/lib/phoenix/admin-token'], capture_output=True)
    assert denied.returncode != 0
    untrusted = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        untrusted.open('https://127.0.0.1:8443/healthz', timeout=5)
    except urllib.error.URLError:
        pass
    else:
        raise AssertionError('Untrusted certificate accepted')
    for headers, code in [({}, 401), ({'Authorization': 'Bearer ' + 'b' * 64}, 401),
                          ({'Authorization': 'Bearer ' + token, 'Origin': 'https://untrusted.example'}, 403)]:
        try:
            request('api/v1/policy', headers=headers)
        except urllib.error.HTTPError as error:
            assert error.code == code, (headers.keys(), error.code)
        else:
            raise AssertionError('Authorization or Origin check bypassed')
    assert request('api/v1/auth/status', headers={})['password_login'] is True
    run('systemctl', 'kill', '--kill-who=main', '--signal=KILL', 'phoenix-control.service')
    wait(lambda: Path('/proc/sys/net/ipv4/ip_forward').read_text().strip() == '0', 10)
    run('nft', 'list', 'table', 'inet', 'phoenix_stop')
    wait(lambda: healthz()['ready'])
    assert request('api/v1/status')['direct'] is False
    print('VM PASS: certificate trust, Bearer/password auth, Origin, private state isolation and worker SIGKILL fail-closed recovery', flush=True)

    run(PHOENIX, 'update', 'sign', '--payload', '/opt/vm/factory.zip', '--output', '/opt/vm/valid.phx', '--key', key,
        '--version', 'vm-valid', '--sequence', '1')
    upload('/opt/vm/valid.phx')
    wait(lambda: state().get('phase') == 'active')
    wait(lambda: healthz()['ready'])
    active = Path('/opt/phoenix').resolve()
    assert active.name.startswith('1-') and healthz()['release_id'] == active.name
    print('VM PASS: signed format-2 upload, actual systemd stop/start, release switch and HTTPS health gate', flush=True)
    for sequence in range(2, 6):
        release = f'/opt/vm/valid-{sequence}.phx'
        run(PHOENIX, 'update', 'sign', '--payload', '/opt/vm/factory.zip', '--output', release, '--key', key,
            '--version', f'vm-valid-{sequence}', '--sequence', str(sequence))
        upload(release)
        wait(lambda: state().get('phase') == 'active' and state().get('max_sequence') == sequence)
        wait(lambda: healthz()['ready'])
        active = Path('/opt/phoenix').resolve()
        assert active.name.startswith(f'{sequence}-')
    try:
        request('api/v1/firmware', Path('/opt/vm/valid-2.phx').read_bytes(), True)
    except urllib.error.HTTPError as error:
        assert error.code == 400, error.code
    else:
        raise AssertionError('Replayed release accepted')
    assert state()['phase'] == 'active' and Path('/opt/phoenix').resolve() == active
    print('VM PASS: five sequential signed updates and service restarts; replay rejected', flush=True)

    # Valid signature and bundle, but the "binary" cannot serve: startup health must fail.
    run(PHOENIX, 'package', 'build', '/opt/vm/broken.zip', '--binary', '/usr/bin/false', '--deploy-dir', DEPLOY)
    run(PHOENIX, 'update', 'sign', '--payload', '/opt/vm/broken.zip', '--output', '/opt/vm/broken.phx', '--key', key,
        '--version', 'vm-broken', '--sequence', '6')
    upload('/opt/vm/broken.phx')
    wait(lambda: state().get('phase') == 'rolled_back', 180)
    assert state()['error'] == 'activation_failed', state()
    wait(lambda: healthz()['ready'])
    assert Path('/opt/phoenix').resolve() == active
    assert request('api/v1/status')['direct'] is False
    print('VM PASS: broken signed release rejected by real startup health, previous release restored and traffic blocked', flush=True)
    run('systemctl', 'stop', 'phoenix.service', 'phoenix-control.service', timeout=180)
    assert Path('/proc/sys/net/ipv4/ip_forward').read_text().strip() == '0'
    run('nft', 'list', 'table', 'inet', 'phoenix_stop')
    run('systemctl', 'start', 'phoenix.service', timeout=180)
    wait(lambda: healthz()['ready'])
    print('VM PASS: restart and stop guard verified', flush=True)

    # Durable journal + new symlink simulates interruption between switch and health.
    run('systemctl', 'stop', 'phoenix.service', 'phoenix-control.service', timeout=180)
    interrupted = state()
    interrupted.update(phase='activating', previous=active.name)
    write_state(interrupted)
    switch = Path('/opt/phoenix.switch')
    os.symlink(Path('/opt/phoenix-releases') / interrupted['next'], switch)
    os.replace(switch, '/opt/phoenix')
    assert Path('/opt/phoenix').resolve().name == interrupted['next'] != active.name
    marker.write_text(active.name)
    os.sync()
    print('VM: rebooting with interrupted update journal', flush=True)
    run('systemctl', 'reboot')
    os._exit(0)
except Exception as error:
    print('VM TEST FAILED: ' + type(error).__name__ + ': ' + str(error), flush=True)
    print(subprocess.run(['journalctl', '-b', '--no-pager', '-n', '90', '-u', 'phoenix.service', '-u', 'phoenix-control.service',
                          '-u', 'phoenix-update.service', '-u', 'phoenix-update-recover.service'], capture_output=True, text=True).stdout, flush=True)
finally:
    subprocess.run(['systemctl', 'poweroff'], check=False)
