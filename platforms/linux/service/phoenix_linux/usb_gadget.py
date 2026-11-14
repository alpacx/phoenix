"""Opt-in configfs USB Ethernet. Never changes port role, VBUS or foreign gadgets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
from .firewall import interface
from .jsonutil import loads as strict_json

ROOT = Path('/sys/kernel/config/usb_gadget')
UDCS = Path('/sys/class/udc')
PRODUCT = 'Phoenix USB Ethernet'


def settings(config):
    value = config.get('usb_gadget', {})
    if value.get('enabled') is not True:
        raise ValueError('usb_not_enabled')
    result = dict(value)
    if result.get('function') not in ('ncm', 'ecm'):
        raise ValueError('usb_function_must_be_ncm_or_ecm')
    for key in ('vendor_id', 'product_id'):
        if not re.fullmatch(r'0x[0-9a-fA-F]{4}', str(result.get(key, ''))) or int(result[key], 16) == 0:
            raise ValueError('invalid_usb_' + key)
    for key in ('udc', 'serial'):
        if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}', str(result.get(key, ''))):
            raise ValueError('invalid_usb_' + key)
    if result['udc'] in ('.', '..'):
        raise ValueError('invalid_usb_udc')
    result['interface'] = interface(config['interfaces']['usb'])
    if result['interface'] in [config['interfaces'][k] for k in ('uplink', 'ap', 'vpn')]:
        raise ValueError('usb_interface_role_conflict')
    return result


def macs(serial):
    digest = hashlib.sha256(serial.encode('ascii')).digest()
    return tuple(':'.join(f'{x:02x}' for x in bytes([prefix]) + digest[:5]) for prefix in (2, 6))


class Gadget:
    def __init__(self, config, root=ROOT, udcs=UDCS, net=Path('/sys/class/net')):
        self.options = settings(config)
        self.root, self.udcs, self.net = Path(root), Path(udcs), Path(net)
        self.path = self.root / 'phoenix'
        self.function = self.options['function'] + '.usb0'

    def mkdir(self, relative):
        (self.path / relative).mkdir()

    def write(self, relative, value):
        (self.path / relative).write_text(str(value) + '\n')

    def rmdir(self, relative):
        (self.path / relative).rmdir()

    def start(self):
        if self.options.get('vbus_verified') is not True:
            raise ValueError('usb_vbus_not_verified')
        if not self.root.is_dir() or not (self.udcs / self.options['udc']).is_dir():
            raise ValueError('usb_configfs_or_udc_unavailable')
        # Do not adopt Radxa's gadget (which may include ADB), or silently replace ours.
        if self.path.exists() or self.path.is_symlink():
            raise ValueError('usb_gadget_already_exists')
        if (self.net / self.options['interface']).exists():
            raise ValueError('usb_interface_already_exists')
        for other in self.root.iterdir():
            binding = other / 'UDC'
            if binding.exists() and binding.read_text().strip() == self.options['udc']:
                raise ValueError('usb_udc_owned_by_another_gadget')
        created, linked = [], False
        self.mkdir('')
        try:
            for key, val in [('idVendor', self.options['vendor_id']), ('idProduct', self.options['product_id']),
                             ('bcdDevice', '0x0100'), ('bcdUSB', '0x0200')]:
                self.write(key, val)
            for directory in ('strings/0x409', 'configs/c.1', 'configs/c.1/strings/0x409', 'functions/' + self.function):
                self.mkdir(directory)
                created.append(directory)
            for key, val in [('manufacturer', 'Phoenix'), ('product', PRODUCT), ('serialnumber', self.options['serial'])]:
                self.write('strings/0x409/' + key, val)
            self.write('configs/c.1/strings/0x409/configuration', 'USB Ethernet')
            # Separately powered target. These descriptors do NOT switch physical VBUS.
            self.write('configs/c.1/bmAttributes', '0xc0')
            self.write('configs/c.1/MaxPower', '0')
            dev, host = macs(self.options['serial'])
            for key, val in [('dev_addr', dev), ('host_addr', host), ('ifname', self.options['interface'])]:
                self.write('functions/' + self.function + '/' + key, val)
            (self.path / 'configs/c.1' / self.function).symlink_to(self.path / 'functions' / self.function)
            linked = True
            # Binding is deliberately last; failures must not expose a partial gadget.
            self.write('UDC', self.options['udc'])
        except Exception:
            self.write('UDC', '')
            if linked:
                (self.path / 'configs/c.1' / self.function).unlink()
            for directory in reversed(created):
                self.rmdir(directory)
            self.rmdir('')
            raise

    def stop(self):
        if not self.path.exists():
            return
        if self.path.is_symlink() or (self.path / 'strings/0x409/product').read_text().strip() != PRODUCT:
            raise ValueError('usb_gadget_not_owned')
        if (self.path / 'strings/0x409/serialnumber').read_text().strip() != self.options['serial']:
            raise ValueError('usb_gadget_identity_mismatch')
        if {p.name for p in (self.path / 'functions').iterdir()} != {self.function}:
            raise ValueError('usb_gadget_functions_changed')
        if {p.name for p in (self.path / 'configs').iterdir()} != {'c.1'}:
            raise ValueError('usb_gadget_configurations_changed')
        if (self.path / 'UDC').read_text().strip() not in ('', self.options['udc']):
            raise ValueError('usb_gadget_binding_changed')
        link = self.path / 'configs/c.1' / self.function
        if not link.is_symlink() or link.resolve() != (self.path / 'functions' / self.function).resolve():
            raise ValueError('usb_gadget_link_changed')
        self.write('UDC', '')
        (self.path / 'configs/c.1' / self.function).unlink()
        for directory in ('configs/c.1/strings/0x409', 'configs/c.1', 'functions/' + self.function, 'strings/0x409', ''):
            self.rmdir(directory)


def owned_binding(name, root=ROOT):
    path = Path(root) / 'phoenix'
    try:
        if (path / 'strings/0x409/product').read_text().strip() != PRODUCT or not (path / 'UDC').read_text().strip():
            return False
        functions = list((path / 'functions').iterdir())
        return len(functions) == 1 and functions[0].name in ('ncm.usb0', 'ecm.usb0') and (functions[0] / 'ifname').read_text().strip() == name
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('inspect', 'start', 'stop'))
    parser.add_argument('--target-config', default='/etc/phoenix/target.json')
    args = parser.parse_args()
    if platform.system() != 'Linux':
        raise SystemExit('Linux target required; no host networking changed')
    if args.action == 'inspect':
        controllers = []
        for path in sorted(UDCS.glob('*')):
            item = {'name': path.name}
            for key in ('state', 'current_speed', 'maximum_speed', 'function'):
                try:
                    item[key] = (path / key).read_text().strip()
                except OSError:
                    item[key] = None
            controllers.append(item)
        print(json.dumps({'udcs': controllers,
                          'configfs_available': ROOT.is_dir(),
                          'gadgets': sorted(p.name for p in ROOT.glob('*')),
                          'electrical_safety_verified': False}))
        return
    if os.geteuid() != 0:
        raise SystemExit('Root on the identified target required')
    config = strict_json(Path(args.target_config).read_text())
    if not config.get('expected_model') or config['expected_model'] != Path('/proc/device-tree/model').read_text().strip('\0\n'):
        raise SystemExit('Target model mismatch')
    if not any(' /sys/kernel/config ' in line and ' - configfs ' in line for line in Path('/proc/self/mountinfo').read_text().splitlines()):
        raise SystemExit('configfs must already be mounted at /sys/kernel/config')
    getattr(Gadget(config), args.action)()


if __name__ == '__main__':
    main()
