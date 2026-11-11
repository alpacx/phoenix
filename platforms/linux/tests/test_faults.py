import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from phoenix_linux.controller import Controller
from phoenix_linux.runtime import Runtime
from test_runtime import FakeRunner
from test_policy import NAMES
from test_vpn import KEY


class FaultTests(unittest.TestCase):
    def test_repeated_dns_failures_keep_fixed_country_and_bounded_backoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(NAMES, FakeRunner())
            c = Controller(tmp, [{'code':'IT','id':100}], runtime)
            c.settings = {'provider':'nordvpn','nord_key':KEY,'country':'IT'}
            c.want_connected = True
            with patch.object(runtime, 'nord_request', side_effect=ValueError('dns unavailable')):
                for attempt in range(15):
                    now = 100 + attempt * 100
                    c.retry_at = now - 1
                    with patch('phoenix_linux.controller.time.monotonic', return_value=now):
                        c.tick()
                    self.assertEqual(runtime.mode, 'blocked')
                    self.assertEqual(c.settings['country'], 'IT')
                    self.assertLessEqual(c.retry_at - now, 60)
                    self.assertFalse(c.enabled)
            c.command({'action':'disconnect'})
            self.assertIsNone(c.retry_at)

    def test_corrupt_credentials_fail_without_exposing_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'vpn-private.json'
            path.write_text('{"secret":"test-only-corrupt"')
            path.chmod(0o600)
            with self.assertRaises(json.JSONDecodeError) as error:
                Controller(tmp, [])
            self.assertNotIn('test-only-corrupt',str(error.exception))

    def test_confirmed_tunnel_loss_does_not_wait_for_initial_handshake_grace(self):
        from test_vpn import PROFILE
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Runtime(NAMES,FakeRunner(),clock=lambda:1010)
            c=Controller(tmp,[],runtime)
            c.command({'action':'wireguard','profile':PROFILE})
            c.tick()
            self.assertTrue(c.connected_recorded)
            runtime.clock=lambda:1500
            c.tick()
            self.assertEqual(runtime.mode,'blocked')
            self.assertFalse(c.enabled)
            self.assertIsNotNone(c.retry_at)
