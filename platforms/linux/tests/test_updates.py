import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
from phoenix_linux.package import build
from phoenix_linux.updates import sign, verify, Updates


class UpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.key, cls.pub = cls.root / 'private.pem', cls.root / 'public.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'ED25519', '-out', str(cls.key)], check=True, capture_output=True)
        cls.key.chmod(0o600)
        subprocess.run(['openssl', 'pkey', '-in', str(cls.key), '-pubout', '-out', str(cls.pub)], check=True, capture_output=True)
        cls.payload = cls.root / 'payload.zip'
        build(cls.payload)
        cls.envelope = cls.root / 'release.phx'
        sign(cls.payload, cls.envelope, cls.key, 2, 'test-2')
        cls.data = cls.envelope.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def updater(self, tmp):
        root = Path(tmp)
        releases = root / 'releases'
        (releases / 'factory').mkdir(parents=True)
        current = root / 'current'
        current.symlink_to(releases / 'factory')
        return Updates(releases, current, root / 'state', self.pub)

    def test_real_signature_and_modified_payload(self):
        meta, _ = verify(self.data, self.pub)
        self.assertEqual(meta['sequence'], 2)
        for changed in ('payload.zip', 'release.json', 'signature.bin'):
            out = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(self.data)) as source, zipfile.ZipFile(out, 'w') as target:
                for item in source.infolist():
                    content = source.read(item)
                    if item.filename == changed:
                        content = bytes([content[0] ^ 1]) + content[1:]
                    target.writestr(item, content)
            with self.assertRaises((ValueError, zipfile.BadZipFile)):
                verify(out.getvalue(), self.pub)

    def test_wrong_key_rejected(self):
        other_key, other_pub = self.root / 'other.key', self.root / 'other.pub'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'ED25519', '-out', str(other_key)], check=True, capture_output=True)
        subprocess.run(['openssl', 'pkey', '-in', str(other_key), '-pubout', '-out', str(other_pub)], check=True, capture_output=True)
        with self.assertRaises(ValueError):
            verify(self.data, other_pub)

    def test_activate_and_replay_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            update = self.updater(tmp)
            self.assertEqual(update.stage(self.data)['phase'], 'staged')
            calls = []
            result = update.activate(calls.append, lambda name: update.current.resolve().name == name)
            self.assertEqual(result['phase'], 'active')
            self.assertEqual(calls, ['stop', 'start'])
            with self.assertRaises(ValueError):
                update.stage(self.data)

    def test_failed_health_rolls_back_and_keeps_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            update = self.updater(tmp)
            update.stage(self.data)
            with self.assertRaises(ValueError):
                update.activate(lambda _: None, lambda _: False)
            self.assertEqual(update.current.resolve().name, 'factory')
            self.assertEqual(update.status()['phase'], 'rolled_back')
            self.assertEqual(update.status()['max_sequence'], 2)
            with self.assertRaises(ValueError):
                update.stage(self.data)

    def test_interrupted_activation_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            update = self.updater(tmp)
            update.stage(self.data)
            state = update.vault.load()
            state['phase'] = 'activating'
            update.vault.save(state)
            update.switch(state['next'])
            self.assertTrue(update.recover())
            self.assertEqual(update.current.resolve().name, 'factory')
            self.assertFalse(update.recover())

    def test_http_signed_upload_blocks_and_freezes_commands(self):
        from http.server import HTTPServer
        import http.client
        import threading
        from types import SimpleNamespace
        from phoenix_linux.controller import Controller
        from phoenix_linux.server import handler
        from phoenix_linux.store import RevisionConflict
        with tempfile.TemporaryDirectory() as tmp:
            update = self.updater(tmp)
            controller = Controller(Path(tmp) / 'control', [])
            controller.updates = update
            calls = []
            controller.runtime = SimpleNamespace(block=lambda _: calls.append('block'),
                run=lambda args: calls.append(args))
            server = HTTPServer(('127.0.0.1', 0), handler(controller, 'a' * 64))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def upload(data):
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
                    connection.request('POST', '/api/v1/firmware', data,
                        {'Authorization': 'Bearer ' + 'a' * 64, 'Content-Type': 'application/octet-stream'})
                    response = connection.getresponse()
                    response.read()
                    status = response.status
                    connection.close()
                    return status
                self.assertEqual(upload(b'not signed'), 400)
                self.assertEqual(calls, [])
                self.assertFalse(controller.updating)
                self.assertEqual(upload(self.data), 202)
                self.assertTrue(controller.updating)
                self.assertEqual(calls[0], 'block')
                self.assertEqual(calls[1], ['systemctl', 'start', '--no-block', 'phoenix-update.service'])
                with self.assertRaises(RevisionConflict):
                    controller.submit({'action':'direct'})
                controller.tick()  # Must not reconnect during activation.
                self.assertEqual(len(calls), 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_low_disk_space_rejected_before_staging(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            updater=self.updater(tmp)
            with patch('phoenix_linux.updates.shutil.disk_usage',return_value=SimpleNamespace(free=1)):
                with self.assertRaisesRegex(ValueError,'insufficient_update_space'):
                    updater.stage(self.data)
            self.assertEqual(updater.current.resolve().name,'factory')
            self.assertIsNone(updater.status()['phase'])
            self.assertEqual(len(list(updater.releases.iterdir())),1)
