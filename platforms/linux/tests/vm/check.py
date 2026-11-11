"""Run only inside the disposable QEMU guest. Never execute on a real target."""
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=90).stdout


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


try:
    model = Path('/proc/device-tree/model').read_text().strip('\0\n')
    if 'dummy-virt' not in model and 'QEMU' not in model:
        raise RuntimeError('Not the isolated QEMU target')
    sys.path.insert(0, '/opt/source/platforms/linux/service')
    from phoenix_linux.package import build
    from phoenix_linux.updates import sign
    from phoenix_linux.install import install
    for name in ('testwan', 'testap', 'testusb'):
        run('ip', 'link', 'add', name, 'type', 'dummy')
        run('ip', 'link', 'set', name, 'up')
    run('ip', 'address', 'add', '192.0.2.10/24', 'dev', 'testwan')
    run('ip', 'route', 'add', 'default', 'via', '192.0.2.1', 'dev', 'testwan')
    marker = Path('/opt/vm/reboot-check')
    if marker.exists():
        run('systemctl', 'start', 'phoenix.service')
        context = ssl.create_default_context(cafile='/etc/phoenix/admin-cert.pem')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
        def ready_after_reboot():
            with opener.open('https://127.0.0.1:8443/healthz',timeout=5) as response:
                return json.loads(response.read())['ready']
        wait(ready_after_reboot)
        state = json.loads(Path('/var/lib/phoenix/update-state.json').read_text())
        assert state['phase'] == 'rolled_back' and state['error'] == 'interrupted_update'
        assert Path('/opt/phoenix').resolve().name == marker.read_text()
        assert state['max_sequence'] == 6
        print('VM ALL CHECKS PASS: actual reboot recovered interrupted update before starting services',flush=True)
        run('systemctl','poweroff')
        sys.exit(0)
    run('useradd', '--system', '--no-create-home', '--shell', '/usr/sbin/nologin', 'phoenix-web')
    key, pub = '/opt/vm/private.pem', '/opt/vm/public.pem'
    run('openssl', 'genpkey', '-algorithm', 'ED25519', '-out', key)
    Path(key).chmod(0o600)
    run('openssl', 'pkey', '-in', key, '-pubout', '-out', pub)
    config = Path('/opt/vm/target.json')
    config.write_text(json.dumps({'expected_model': model, 'interfaces': {'ap':'testap','usb':'testusb','uplink':'testwan','vpn':'phwg0'}}))
    build('/opt/vm/factory.zip')
    install('/opt/vm/factory.zip', config, pub)
    run('systemctl', 'mask', 'systemd-networkd-wait-online.service', 'NetworkManager-wait-online.service')
    run('systemctl', 'daemon-reload')
    run('systemctl', 'start', 'phoenix.service')
    context = ssl.create_default_context(cafile='/etc/phoenix/admin-cert.pem')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))
    token = Path('/var/lib/phoenix/admin-token').read_text().strip()
    def request(path, body=None, binary=False):
        headers = {'Authorization':'Bearer '+token}
        if body is not None:
            headers['Content-Type'] = 'application/octet-stream' if binary else 'application/json'
            if not binary:
                body = json.dumps(body).encode()
        with opener.open(urllib.request.Request('https://127.0.0.1:8443/'+path, data=body, headers=headers),timeout=20) as response:
            return json.loads(response.read())
    wait(lambda: request('healthz')['ready'])
    frontend = run('systemctl','show','phoenix.service','-p','MainPID','--value').strip()
    proc = Path('/proc/'+frontend+'/status').read_text()
    assert 'Uid:\t0\t' not in proc and 'CapEff:\t0000000000000000' in proc
    assert request('api/v1/status')['direct'] is False
    print('VM PASS: systemd boot, unprivileged HTTPS, trusted certificate, real root worker and blocked initial network',flush=True)
    denied = subprocess.run(['runuser','-u','phoenix-web','--','cat','/var/lib/phoenix/admin-token'],capture_output=True)
    assert denied.returncode != 0
    untrusted = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        untrusted.open('https://127.0.0.1:8443/healthz',timeout=5)
    except urllib.error.URLError:
        pass
    else:
        raise AssertionError('Untrusted certificate accepted')
    for headers, code in [({},401),({'Authorization':'Bearer '+token,'Origin':'https://untrusted.example'},403)]:
        try:
            opener.open(urllib.request.Request('https://127.0.0.1:8443/api/v1/policy',headers=headers),timeout=5)
        except urllib.error.HTTPError as error:
            assert error.code == code
        else:
            raise AssertionError('Authorization or Origin check bypassed')
    run('systemctl','kill','--kill-who=main','--signal=KILL','phoenix-control.service')
    wait(lambda: Path('/proc/sys/net/ipv4/ip_forward').read_text().strip() == '0',10)
    wait(lambda: request('healthz')['ready'])
    assert request('api/v1/status')['direct'] is False
    print('VM PASS: certificate trust, authentication, Origin, private state isolation and worker SIGKILL recovery',flush=True)

    sign('/opt/vm/factory.zip','/opt/vm/valid.phx',key,1,'vm-valid')
    try:
        request('api/v1/firmware',Path('/opt/vm/valid.phx').read_bytes(),True)
    except OSError:
        pass  # The service may stop before the accepted response reaches the client.
    state = Path('/var/lib/phoenix/update-state.json')
    wait(lambda: json.loads(state.read_text()).get('phase') == 'active')
    wait(lambda: request('healthz')['ready'])
    active = Path('/opt/phoenix').resolve()
    assert active.name.startswith('1-')
    print('VM PASS: signed upload, actual systemd stop/start, release switch and HTTPS health gate',flush=True)
    for sequence in range(2,6):
        release='/opt/vm/valid-'+str(sequence)+'.phx'
        sign('/opt/vm/factory.zip',release,key,sequence,'vm-valid-'+str(sequence))
        try:
            request('api/v1/firmware',Path(release).read_bytes(),True)
        except OSError:
            pass
        wait(lambda: json.loads(state.read_text()).get('phase')=='active' and json.loads(state.read_text()).get('max_sequence')==sequence)
        wait(lambda: request('healthz')['ready'])
        active=Path('/opt/phoenix').resolve()
    print('VM PASS: five sequential signed updates and service restarts',flush=True)
    shutil.copytree('/opt/source','/opt/vm/broken-source')
    broken = Path('/opt/vm/broken-source/platforms/linux/service/phoenix_linux/server.py')
    broken.write_text("raise RuntimeError('deliberately broken test release')\n")
    build('/opt/vm/broken.zip',root='/opt/vm/broken-source')
    sign('/opt/vm/broken.zip','/opt/vm/broken.phx',key,6,'vm-broken')
    try:
        request('api/v1/firmware',Path('/opt/vm/broken.phx').read_bytes(),True)
    except OSError:
        pass
    wait(lambda: json.loads(state.read_text()).get('phase') == 'rolled_back',150)
    wait(lambda: request('healthz')['ready'])
    assert Path('/opt/phoenix').resolve() == active
    assert request('api/v1/status')['direct'] is False
    print('VM PASS: broken signed release rejected by real startup health, previous release restored and traffic blocked',flush=True)
    run('systemctl','stop','phoenix.service','phoenix-control.service')
    assert Path('/proc/sys/net/ipv4/ip_forward').read_text().strip() == '0'
    run('nft','list','table','inet','phoenix_stop')
    run('systemctl','start','phoenix.service')
    wait(lambda: request('healthz')['ready'])
    print('VM PASS: restart and stop guard verified',flush=True)
    # Durable journal + new symlink simulates interruption between switch and health.
    run('systemctl','stop','phoenix.service','phoenix-control.service')
    from phoenix_linux.updates import from_config
    updater = from_config('/etc/phoenix/updates.json')
    interrupted = updater.vault.load()
    interrupted.update(phase='activating',previous=active.name)
    updater.vault.save(interrupted)
    updater.switch(interrupted['next'])
    marker.write_text(active.name)
    print('VM: rebooting with interrupted update journal',flush=True)
    run('systemctl','reboot')
    os._exit(0)
except Exception as error:
    print('VM TEST FAILED: '+type(error).__name__+': '+str(error),flush=True)
    print(subprocess.run(['journalctl','-b','--no-pager','-n','90','-u','phoenix.service','-u','phoenix-control.service','-u','phoenix-update.service','-u','phoenix-update-recover.service'],capture_output=True,text=True).stdout,flush=True)
finally:
    subprocess.run(['systemctl','poweroff'],check=False)
