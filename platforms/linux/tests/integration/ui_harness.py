"""Disposable HTTPS target for the browser regression (tests/browser).

Runs the Rust `phoenix control` (root) and `phoenix frontend` (phoenix-web) in a
phoenix-linux-test:local container exactly as the systemd units do, serving
https://127.0.0.1:8443 inside the container's own network namespace. Browser
containers join it with `--network container:NAME`; no port is published and
host networking is never used. Disposable self-signed certificate and a
disposable test password only, never device credentials; the admin token stays
inside the container.

SYS_ADMIN is used only inside the container: tmpfs on /sys/firmware to fake the
device-tree model, and a writable /proc/sys for the worker's ip_forward.

Usage (repo root, after tools/rust-linux.sh build --release):
  PHOENIX_TEST_PASSWORD=... python3 platforms/linux/tests/integration/ui_harness.py start [--name N] [--binary F]
      fresh state, password set to $PHOENIX_TEST_PASSWORD (12-128 characters)
  python3 platforms/linux/tests/integration/ui_harness.py reset [--name N]
      fresh state, initial password "phoenix" with forced change
  python3 platforms/linux/tests/integration/ui_harness.py stop [--name N]
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]
IMAGE = 'phoenix-linux-test:local'
MODEL = 'Phoenix UI Harness'
NAMES = {'ap': 'testap', 'usb': 'testusb', 'uplink': 'eth0', 'vpn': 'phwg0'}
PHOENIX = '/opt/phoenix-releases/test/bin/phoenix'


def docker(*args, data=None, check=True, timeout=120):
    result = subprocess.run(['docker', *args], input=data, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise SystemExit(f'docker {args[0]} failed: {result.stderr.strip()}')
    return result


def sh(name, script, data=None, check=True):
    return docker('exec', '-i', name, 'sh', '-ec', script, data=data, check=check)


def logs(name):
    for role in ('worker', 'frontend'):
        print(f'--- {role} log ---\n' + sh(name, f'tail -c 4000 /tmp/{role}.log', check=False).stdout)


def prepare(name):
    sh(name, f'''
mount -o remount,rw /proc/sys
mount -t tmpfs tmpfs /sys/firmware
mkdir -p /sys/firmware/devicetree/base
printf '{MODEL}\\0' > /sys/firmware/devicetree/base/model
for link in {NAMES['ap']} {NAMES['usb']}; do ip link add "$link" type dummy; ip link set "$link" up; done
useradd --system --no-create-home --shell /usr/sbin/nologin phoenix-web
mkdir -p {Path(PHOENIX).parent} /etc/phoenix /var/lib/phoenix /run/phoenix-control /run/creds
install -m 0755 /mnt/phoenix {PHOENIX}
chmod 0700 /var/lib/phoenix /etc/phoenix && chgrp phoenix-web /run/phoenix-control && chmod 0750 /run/phoenix-control
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=Phoenix -addext subjectAltName=IP:127.0.0.1 \\
  -addext basicConstraints=critical,CA:FALSE -keyout /etc/phoenix/admin-key.pem -out /etc/phoenix/admin-cert.pem 2>/dev/null
umask 077; cat > /etc/phoenix/target.json
''', data=json.dumps({'expected_model': MODEL, 'interfaces': NAMES}))


def launch(name):
    """Fresh state, then worker (root, Group=phoenix-web) and frontend (phoenix-web) as the units do."""
    sh(name, f'''umask 077
for role in frontend worker; do
  [ -f /tmp/$role.pid ] || continue
  pid=$(cat /tmp/$role.pid); kill -TERM "$pid" 2>/dev/null || true
  for i in $(seq 1 100); do [ -d /proc/$pid ] || break; sleep 0.1; done
  [ ! -d /proc/$pid ] || {{ echo "$role did not stop"; exit 1; }}
done
rm -rf /var/lib/phoenix/* /run/phoenix-control/* /run/creds/* /tmp/cookies
ip link delete phwg0 2>/dev/null || true
nft delete table inet phoenix_stop 2>/dev/null || true
nohup setpriv --regid phoenix-web --clear-groups {PHOENIX} control --state-dir /var/lib/phoenix \\
  --target-config /etc/phoenix/target.json --worker-socket /run/phoenix-control/control.sock >/tmp/worker.log 2>&1 &
echo $! > /tmp/worker.pid
for i in $(seq 1 100); do [ -S /run/phoenix-control/control.sock ] && break; sleep 0.1; done
[ -S /run/phoenix-control/control.sock ] || {{ echo 'worker socket missing'; exit 1; }}
for f in admin-token:/var/lib/phoenix/admin-token tls-key:/etc/phoenix/admin-key.pem tls-cert:/etc/phoenix/admin-cert.pem; do
  install -o phoenix-web -g phoenix-web -m 0400 "${{f#*:}}" "/run/creds/${{f%%:*}}"; done
nohup setpriv --reuid phoenix-web --regid phoenix-web --init-groups {PHOENIX} frontend \\
  --token-file /run/creds/admin-token --tls-key /run/creds/tls-key --tls-cert /run/creds/tls-cert >/tmp/frontend.log 2>&1 &
echo $! > /tmp/frontend.pid
''')
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        result = sh(name, 'curl -sk --noproxy "*" --max-time 2 https://127.0.0.1:8443/healthz', check=False)
        if result.returncode == 0 and json.loads(result.stdout or '{}').get('ready') is True:
            return
        time.sleep(0.25)
    logs(name)
    raise SystemExit('Phoenix services not ready')


def post(name, path, body):
    """Browser-like POST (Origin + session cookie jar); the body travels on stdin."""
    result = sh(name, f'''curl -sk --noproxy "*" --max-time 20 -c /tmp/cookies -b /tmp/cookies \\
  -H 'Origin: https://127.0.0.1:8443' -H 'Content-Type: application/json' --data-binary @- \\
  -o /tmp/response -w '%{{http_code}}' https://127.0.0.1:8443{path}''', data=json.dumps(body))
    if result.stdout.strip() != '200':
        raise SystemExit(f'POST {path}: HTTP {result.stdout.strip()} {sh(name, "cat /tmp/response").stdout[:200]}')


def set_password(name, password):
    post(name, '/api/v1/auth/login', {'password': 'phoenix'})
    post(name, '/api/v1/auth/password', {'current_password': 'phoenix', 'new_password': password})
    post(name, '/api/v1/auth/logout', {})
    sh(name, 'rm -f /tmp/cookies /tmp/response')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('action', choices=('start', 'reset', 'stop'))
    parser.add_argument('--name', default='phoenix-ui-review')
    parser.add_argument('--binary', default=str(ROOT / 'platforms/linux/rust/target/release/phoenix'))
    args = parser.parse_args()
    if args.action == 'stop':
        docker('rm', '-f', args.name, check=False)
        return
    if args.action == 'reset':
        launch(args.name)
        print(f'{args.name}: fresh state, initial password')
        return
    password = os.environ.get('PHOENIX_TEST_PASSWORD', '')
    if not 12 <= len(password) <= 128:
        raise SystemExit('Set PHOENIX_TEST_PASSWORD (12-128 characters, disposable)')
    binary = Path(args.binary).resolve()
    if not binary.is_file():
        raise SystemExit('Build first: tools/rust-linux.sh build --release')
    if docker('image', 'inspect', IMAGE, check=False).returncode:
        docker('build', '-q', '-t', IMAGE, str(ROOT / 'platforms/linux/tests/integration'), timeout=900)
    docker('rm', '-f', args.name, check=False)
    docker('run', '-d', '--init', '--name', args.name, '--cap-add', 'NET_ADMIN', '--cap-add', 'SYS_ADMIN',
           '--security-opt', 'apparmor=unconfined',
           '--mount', f'type=bind,source={binary},target=/mnt/phoenix,readonly', IMAGE, 'sleep', 'infinity')
    try:
        prepare(args.name)
        launch(args.name)
        set_password(args.name, password)
    except BaseException:
        docker('rm', '-f', args.name, check=False)
        raise
    print(f'{args.name}: https://127.0.0.1:8443 ready (join with --network container:{args.name})')


if __name__ == '__main__':
    main()
