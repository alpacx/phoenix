import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from phoenix_linux.controller import Controller
from phoenix_linux.rpc import LocalAPI, RemoteAPI, ControlServer


@unittest.skipUnless(hasattr(socket, 'SO_PEERCRED'), 'Linux peer credentials required')
class RPCTests(unittest.TestCase):
    def test_allowlist_and_peer_uid(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = Controller(Path(tmp) / 'state', [])
            path = Path(tmp) / 'control.sock'
            server = ControlServer(path, LocalAPI(c), os.getuid())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                remote = RemoteAPI(path)
                self.assertEqual(remote.call('policy'), c.policy())
                self.assertFalse(remote.call('capabilities')['network_initialized'])
                with self.assertRaises(ValueError):
                    remote.call('execute', {'argv':['sh']})
                server.allowed_uid = os.getuid() + 1
                with self.assertRaises((OSError, ValueError)):
                    remote.call('policy')
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_policy_does_not_wait_then_mutate_after_request_timeout(self):
        from phoenix_linux.store import RevisionConflict
        with tempfile.TemporaryDirectory() as tmp:
            controller = Controller(tmp, [])
            entered, release = threading.Event(), threading.Event()
            def hold():
                with controller.lock:
                    entered.set()
                    release.wait(3)
            thread = threading.Thread(target=hold)
            thread.start()
            entered.wait(1)
            try:
                with self.assertRaises(RevisionConflict):
                    LocalAPI(controller).call('save_policy', {})
                self.assertEqual(controller.store.load()['revision'],0)
            finally:
                release.set()
                thread.join()
