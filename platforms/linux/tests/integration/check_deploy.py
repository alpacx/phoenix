"""Validate userspace configuration with real Debian binaries; no radio emulation."""
from pathlib import Path
import subprocess
import tempfile
from phoenix_linux.access_point import render
from phoenix_linux.runtime import Runner
from phoenix_linux.stop_guard import block

if not Path('/.dockerenv').exists():
    raise SystemExit('Run only in the isolated test container')

with tempfile.TemporaryDirectory() as tmp:
    directory = Path(tmp)
    configs = render('wlan0', 'Phoenix-Test', 'test-only-passphrase', 'IT', '103.86.96.100')
    path = directory / 'dnsmasq.conf'
    path.write_text(configs['dnsmasq.conf'])
    subprocess.run(['dnsmasq', '--test', '--conf-file=' + str(path)], check=True)
    forwarding = directory / 'forwarding'
    forwarding.write_text('1')
    block(Runner(), forwarding)
    assert forwarding.read_text() == '0'
    subprocess.run(['nft', 'list', 'table', 'inet', 'phoenix_stop'], check=True, stdout=subprocess.DEVNULL)
subprocess.run(['systemd-analyze', 'verify', *map(str, Path('/workspace/platforms/linux/deploy').glob('*.service'))], check=True)
print('DHCP configuration, stop-guard nft table and four systemd units syntax PASS')
print('Radio/AP remain hardware tests; systemd boot is separately covered by the QEMU VM')

# Exercise the exact profile generator against Bookworm nmcli, without a radio.
from phoenix_linux.station import Station
class ProfileRunner:
    def __call__(self, args, **kwargs):
        if '--offline' in args:
            output = subprocess.run(args, capture_output=True, text=True, check=True)
            assert 'never-default=true' in output.stdout and 'psk-flags=2' in output.stdout
            assert 'test-only-passphrase' not in output.stdout
            self.checked = True
            raise RuntimeError('profile checked; no radio activation')
        return __import__('types').SimpleNamespace(stdout='', returncode=1)
with tempfile.TemporaryDirectory() as tmp:
    runner = ProfileRunner()
    station = Station('wlan0', tmp, runner)
    try:
        station.connect({'mode':'sta','ssid':'Phoenix Test','password':'test-only-passphrase','save':False})
    except RuntimeError:
        pass
    assert runner.checked
print('NetworkManager offline profile generation PASS; radio activation not tested')

# A real NetworkManager daemon loads the generated file from its permitted
# runtime directory. No Wi-Fi device is created or connection activated.
Path('/run/dbus').mkdir(exist_ok=True)
subprocess.run(['dbus-daemon', '--system'], check=True)
manager = subprocess.Popen(['NetworkManager', '--no-daemon'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    import time
    import uuid
    time.sleep(1)
    profiles = Path('/run/NetworkManager/system-connections')
    profiles.mkdir(parents=True, exist_ok=True)
    profile = profiles / 'phoenix-integration.nmconnection'
    identifier = str(uuid.uuid4())
    generated = subprocess.run(['nmcli','--offline','connection','add','type','wifi','ifname','wlan0',
        'con-name','phoenix-integration','connection.uuid',identifier,'ssid','Phoenix Test',
        'connection.autoconnect','no','ipv4.method','auto','ipv4.never-default','yes',
        'ipv4.ignore-auto-dns','yes','ipv6.method','disabled','wifi-sec.key-mgmt','wpa-psk',
        'wifi-sec.psk-flags','2'], capture_output=True, text=True, check=True)
    profile.write_text(generated.stdout)
    profile.chmod(0o600)
    subprocess.run(['nmcli','connection','load',str(profile)],check=True)
    loaded = subprocess.run(['nmcli','-g','connection.uuid','connection','show','uuid',identifier],capture_output=True,text=True,check=True)
    assert loaded.stdout.strip() == identifier
    print('NetworkManager daemon loading generated runtime profile PASS; no radio activation')
finally:
    manager.terminate()
    manager.wait(timeout=10)
