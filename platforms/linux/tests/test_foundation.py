import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from phoenix_linux.preflight import inspect
from phoenix_linux.store import ConfigStore, RevisionConflict


class FoundationTests(unittest.TestCase):
    def test_mac_never_executes_linux_commands(self):
        def forbidden(*args, **kwargs):
            self.fail('Linux command attempted on host')
        self.assertEqual(inspect(system='Darwin', run=forbidden)['blockers'], ['linux_required'])

    def test_inventory_does_not_claim_functional_vpn_or_usb(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sys/class/udc/controller').mkdir(parents=True)
            def run(argv, **kwargs):
                self.assertEqual(argv, ['ip', '-j', 'link', 'show'])
                return subprocess.CompletedProcess(argv, 0, json.dumps([
                    {'ifname': 'end0', 'operstate': 'UP', 'mtu': 1500, 'address': 'private'}]))
            result = inspect(system='Linux', root=root, which=lambda _: '/bin/tool', run=run)
            self.assertEqual(result['blockers'], [])
            self.assertFalse(result['wireguard_verified'])
            self.assertFalse(result['usb_network_verified'])
            self.assertNotIn('address', result['interfaces'][0])
            self.assertEqual(result['usb_device_controllers'], ['controller'])

    def test_ip_failure_is_blocker(self):
        def run(*args, **kwargs):
            raise subprocess.TimeoutExpired('ip', 5)
        result = inspect(system='Linux', which=lambda _: '/bin/tool', run=run)
        self.assertIn('interface_inventory_failed', result['blockers'])

    def test_persistence_conflict_and_validation_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ConfigStore(tmp)
            self.assertFalse(store.load()['desired']['direct'])
            store.save(0, {'schema_version': 1, 'direct': True}, lambda _: None)
            second = ConfigStore(tmp)
            self.assertTrue(second.load()['desired']['direct'])
            with self.assertRaises(RevisionConflict):
                second.save(0, {}, lambda _: None)
            def invalid(_):
                raise ValueError('invalid')
            with self.assertRaises(ValueError):
                store.save(1, {}, invalid)
            self.assertEqual(second.load()['revision'], 1)
            self.assertEqual(os.stat(store.path).st_mode & 0o777, 0o600)

    def test_rejects_public_directory_and_symlink_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o755)
            with self.assertRaises(ValueError):
                ConfigStore(tmp)
            os.chmod(tmp, 0o700)
            (Path(tmp) / 'desired.sqlite3').symlink_to(Path(tmp) / 'other')
            with self.assertRaises(OSError):
                ConfigStore(tmp)


if __name__ == '__main__':
    unittest.main()
