import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile
from phoenix_linux.controller import Controller
from phoenix_linux.runtime import Runtime, NetworkError
from phoenix_linux.package import build, verify
from phoenix_linux.stop_guard import block
from test_runtime import FakeRunner
from test_policy import NAMES
from test_vpn import PROFILE


class LifecycleTests(unittest.TestCase):
    def test_invalid_command_does_not_interrupt_healthy_tunnel(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = FakeRunner()
            c = Controller(tmp, [], Runtime(NAMES, runner, clock=lambda: 1010))
            c.command({'action': 'wireguard', 'profile': PROFILE})
            before = len(runner.calls)
            for body in ({'action': 'wrong'}, {'action': 'wireguard', 'profile': 'broken'}):
                with self.assertRaises(ValueError):
                    c.submit(body)
            self.assertEqual(len(runner.calls), before)
            self.assertTrue(c.enabled)
            self.assertFalse(c.busy)

    def test_failed_diagnostic_does_not_drop_tunnel(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = Controller(tmp, [], Runtime(NAMES, FakeRunner(), clock=lambda: 1010))
            c.command({'action': 'wireguard', 'profile': PROFILE})
            with patch.object(c.runtime, 'verify_exit', side_effect=NetworkError('unavailable')):
                c.submit({'action': 'verify_exit'})
                deadline = time.monotonic() + 2
                while c.busy and time.monotonic() < deadline:
                    time.sleep(0.01)
            self.assertFalse(c.busy)
            self.assertTrue(c.enabled)
            self.assertEqual(c.runtime.mode, 'vpn')
            self.assertEqual(c.error, 'exit_check_failed')
            c.shutdown()
            self.assertEqual(c.runtime.mode, 'blocked')
            self.assertIsNone(c.runtime.profile)
            self.assertFalse(c.want_connected)

    def test_server_sigterm_exits_cleanly_without_printing_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            process = subprocess.Popen([sys.executable, '-m', 'phoenix_linux.server',
                                        '--state-dir', tmp, '--port', '0'],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 3
                while not (Path(tmp) / 'admin-token').exists() and time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail('server exited before startup')
                    time.sleep(0.02)
                self.assertTrue((Path(tmp) / 'admin-token').exists())
                process.terminate()
                out, err = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0, err)
                token = (Path(tmp) / 'admin-token').read_text()
                self.assertNotIn(token, out + err)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)

    def test_stop_guard_disables_forwarding_before_nft_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            forwarding = Path(tmp) / 'forwarding'
            forwarding.write_text('1')
            def failing(*args, **kwargs):
                self.assertEqual(forwarding.read_text(), '0')
                raise NetworkError('nft_unavailable')
            with self.assertRaises(NetworkError):
                block(failing, forwarding)


class PackageTests(unittest.TestCase):
    def test_bundle_is_deterministic_and_excludes_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a.zip', Path(tmp) / 'b.zip'
            manifest = build(a)
            build(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertFalse(manifest['signed'])
            self.assertFalse(any('results/' in name or 'vpn-private' in name or 'admin-token' in name for name in manifest['files']))
            self.assertEqual(verify(a), manifest)

    def test_extra_path_and_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / 'original.zip'
            build(original)
            for name, data in [('../outside', b'bad'), ('shared/web/app.js', b'corrupted')]:
                bad = Path(tmp) / ('bad' + str(len(data)) + '.zip')
                with zipfile.ZipFile(original) as source, zipfile.ZipFile(bad, 'w') as target:
                    for item in source.infolist():
                        target.writestr(item, data if item.filename == name else source.read(item))
                    if name not in source.namelist():
                        target.writestr(name, data)
                with self.assertRaises(ValueError):
                    verify(bad)
