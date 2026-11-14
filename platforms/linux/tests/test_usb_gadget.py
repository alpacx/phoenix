import copy
import tempfile
from pathlib import Path
import unittest
from phoenix_linux.usb_gadget import Gadget, macs, owned_binding, settings

CONFIG = {'interfaces': {'usb': 'phusb0', 'ap': 'wlan0', 'uplink': 'eth0', 'vpn': 'phwg0'},
          'usb_gadget': {'enabled': True, 'function': 'ncm', 'udc': 'udc0', 'serial': 'test-device',
                         'vendor_id': '0x1234', 'product_id': '0x5678', 'vbus_verified': True}}


class FakeConfigfs(Gadget):
    """Models auto-created configfs groups/attributes, not a real USB controller."""
    fail_binding = False
    def mkdir(self, path):
        super().mkdir(path)
        for group in (('strings', 'configs', 'functions') if not path else ('strings',) if path == 'configs/c.1' else ()):
            (self.path / path / group).mkdir()
    def write(self, path, value):
        self.writes.append((path, value))
        if self.fail_binding and path == 'UDC' and value:
            raise OSError('simulated bind failure')
        super().write(path, value)
    def rmdir(self, path):
        directory = self.path / path
        for entry in directory.iterdir():
            if entry.is_dir():
                self_test = entry.name in ('strings', 'configs', 'functions')
                assert self_test and not list(entry.iterdir()), 'Cleanup order violated'
                entry.rmdir()
            else:
                assert not entry.is_symlink(), 'Function link not removed first'
                entry.unlink()  # configfs attributes disappear with their owning group
        super().rmdir(path)


class GadgetTests(unittest.TestCase):
    def make(self, directory, config=None):
        root = Path(directory)
        for name in ('gadgets', 'udcs', 'net'):
            (root / name).mkdir(exist_ok=True)
        (root / 'udcs/udc0').mkdir(exist_ok=True)
        g = FakeConfigfs(config or copy.deepcopy(CONFIG), root / 'gadgets', root / 'udcs', root / 'net')
        g.writes = []
        return g

    def test_ncm_and_ecm_bind_last_stop_owned_only(self):
        for function in ('ncm', 'ecm'):
            with self.subTest(function=function), tempfile.TemporaryDirectory() as tmp:
                config = copy.deepcopy(CONFIG); config['usb_gadget']['function'] = function
                g = self.make(tmp, config); g.start()
                self.assertEqual(g.writes[-1], ('UDC', 'udc0'))
                self.assertTrue(owned_binding('phusb0', g.root))
                self.assertFalse(owned_binding('eth0', g.root))
                g.stop(); self.assertFalse(g.path.exists())
                g.stop()

    def test_vbus_gate_and_foreign_udc_never_mutate(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = copy.deepcopy(CONFIG); config['usb_gadget']['vbus_verified'] = False
            g = self.make(tmp, config)
            with self.assertRaisesRegex(ValueError, 'vbus'):g.start()
            self.assertEqual(g.writes, [])
            g.options['vbus_verified'] = True
            other = g.root / 'radxa'; other.mkdir(); (other / 'UDC').write_text('udc0\n')
            with self.assertRaisesRegex(ValueError, 'another_gadget'):g.start()
            self.assertEqual((other / 'UDC').read_text(), 'udc0\n')
            self.assertFalse(g.path.exists())

    def test_failed_bind_rolls_back_and_can_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = self.make(tmp); g.fail_binding = True
            with self.assertRaises(OSError):g.start()
            self.assertFalse(g.path.exists())
            g.fail_binding = False; g.start(); g.stop()

    def test_unsupported_function_rolls_back_before_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = self.make(tmp)
            original = g.mkdir
            def mkdir(path):
                if path.startswith('functions/'):
                    raise OSError('function unavailable')
                original(path)
            g.mkdir = mkdir
            with self.assertRaises(OSError):g.start()
            self.assertFalse(g.path.exists())
            self.assertNotIn(('UDC', 'udc0'), g.writes)

    def test_existing_or_modified_gadget_not_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = self.make(tmp); g.start()
            with self.assertRaisesRegex(ValueError, 'already_exists'):g.start()
            (g.path / 'functions/ffs.adb').mkdir()
            with self.assertRaisesRegex(ValueError, 'functions_changed'):g.stop()
            self.assertEqual((g.path / 'UDC').read_text().strip(), 'udc0')

    def test_input_validation_and_stable_local_macs(self):
        for key, value in [('udc', '../udc0'), ('serial', 'bad\nserial'), ('vendor_id', '0x0000'), ('function', 'rndis')]:
            config = copy.deepcopy(CONFIG); config['usb_gadget'][key] = value
            with self.assertRaises(ValueError):settings(config)
        dev, host = macs('test-device')
        self.assertNotEqual(dev, host)
        self.assertEqual(macs('test-device'), (dev, host))
        for value in (dev, host):self.assertEqual(int(value[:2], 16) & 3, 2)
