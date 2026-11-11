"""Read-only inventory. Tool presence is never a claim of working networking."""
import json
import platform
import shutil
import subprocess
from pathlib import Path

TOOLS = ('ip', 'nft', 'wg', 'iw', 'hostapd', 'dnsmasq', 'systemctl', 'curl', 'conntrack', 'nmcli', 'openssl')


def read_text(path):
    try:
        return path.read_text().strip().replace('\x00', '')
    except (OSError, UnicodeError):
        return None


def inspect(system=None, root=Path('/'), which=shutil.which, run=subprocess.run):
    system = system or platform.system()
    report = {'system': system, 'kernel': platform.release(),
              'architecture': platform.machine(), 'read_only': True,
              'gateway_verified': False, 'wireguard_verified': False,
              'usb_network_verified': False}
    if system != 'Linux':
        report.update(supported_host=False, blockers=['linux_required'])
        return report
    root = Path(root)
    report['supported_host'] = True
    report['board_model'] = read_text(root / 'proc/device-tree/model')
    report['os_release'] = read_text(root / 'etc/os-release')
    report['tools'] = {name: bool(which(name)) for name in TOOLS}
    report['interfaces'] = []
    if report['tools']['ip']:
        try:
            result = run(['ip', '-j', 'link', 'show'], capture_output=True,
                         text=True, timeout=5, check=True)
            links = json.loads(result.stdout)
            for link in links:
                report['interfaces'].append({
                    'name': link['ifname'], 'state': link.get('operstate'),
                    'mtu': link.get('mtu'),
                    'kind': link.get('linkinfo', {}).get('info_kind')})
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
            report['interface_inventory_error'] = True
    udc = root / 'sys/class/udc'
    try:
        report['usb_device_controllers'] = sorted(p.name for p in udc.iterdir())
    except OSError:
        report['usb_device_controllers'] = []
    report['ipv4_forwarding'] = read_text(root / 'proc/sys/net/ipv4/ip_forward')
    report['blockers'] = ['missing_tool:' + name for name, found in report['tools'].items() if not found]
    if report.get('interface_inventory_error'):
        report['blockers'].append('interface_inventory_failed')
    return report


def main():
    report = inspect()
    print(json.dumps(report, indent=2))
    return 2 if report['blockers'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
