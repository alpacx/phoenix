import json
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from phoenix_linux import usb_bench


class BenchAuthorizationTests(unittest.TestCase):
    def check(self, *, gpio='gpio-35 ( |phoenix-usb-source-o) out lo\n', boot='boot1',
              mode=stat.S_IFREG | 0o600, uid=0, enabled=True):
        values = {'/run/phoenix-usb-bench.json': json.dumps({
            'boot_id': 'boot1', 'udc': 'fe800000.usb', 'acknowledge_unmeasured_vbus': True}),
            '/proc/device-tree/model': 'Radxa ROCK 4C+\0',
            '/proc/sys/kernel/random/boot_id': boot,
            '/proc/device-tree/vbus-typec/status': 'disabled\0',
            '/sys/kernel/debug/gpio': gpio}
        with patch.object(usb_bench.Path, 'lstat', return_value=SimpleNamespace(st_mode=mode, st_uid=uid)), \
             patch.object(usb_bench.Path, 'read_text', lambda path: values[str(path)]):
            return usb_bench.authorized({'bench_unmeasured_vbus': enabled, 'udc': 'fe800000.usb'})

    def test_explicit_current_boot_only(self):
        self.assertTrue(self.check())
        self.assertFalse(self.check(enabled=False))
        self.assertFalse(self.check(boot='boot2'))

    def test_high_missing_or_other_gpio_rejected(self):
        self.assertFalse(self.check(gpio='gpio-35 ( |phoenix-usb-source-o) out hi\n'))
        self.assertFalse(self.check(gpio='gpio-35 ( |vbus-typec) out lo\n'))
        self.assertFalse(self.check(gpio=''))

    def test_private_root_regular_file_required(self):
        self.assertFalse(self.check(uid=1000))
        self.assertFalse(self.check(mode=stat.S_IFREG | 0o644))
        self.assertFalse(self.check(mode=stat.S_IFLNK | 0o600))

    def test_missing_evidence_fails_closed(self):
        with patch.object(usb_bench.Path, 'lstat', side_effect=FileNotFoundError):
            self.assertFalse(usb_bench.authorized({'bench_unmeasured_vbus': True}))
