import subprocess
import unittest
from phoenix_linux.runtime import Runtime, NetworkError
from phoenix_linux.wireguard import parse
from test_vpn import PROFILE, KEY
from test_policy import NAMES, BASE


class FakeRunner:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def __call__(self, argv, data=None, optional=False):
        self.calls.append((argv, data))
        if argv == self.fail:
            raise NetworkError('injected_failure')
        out = ''
        if argv[:4] == ['ip', '-j', 'route', 'get']:
            out = '[{"dev":"end0"}]'
        if argv[:3] == ['wg', 'show', 'phwg0']:
            out = KEY + '\t1000\n'
        return subprocess.CompletedProcess(argv, 0, out)


class RuntimeTests(unittest.TestCase):
    def test_connect_blocks_first_and_keeps_keys_out_of_argv(self):
        runner = FakeRunner()
        runtime = Runtime(NAMES, runner, clock=lambda: 1010)
        runtime.connect(BASE, parse(PROFILE))
        self.assertEqual(runner.calls[2][0], ['nft', '-f', '-'])
        self.assertNotIn('counter accept', runner.calls[2][1])
        self.assertTrue(runtime.handshake())
        self.assertTrue(all(KEY not in ' '.join(argv) for argv, _ in runner.calls))

    def test_failure_does_not_enable_direct(self):
        runner = FakeRunner(fail=['ip', 'link', 'add', 'phwg0', 'type', 'wireguard'])
        runtime = Runtime(NAMES, runner)
        with self.assertRaises(NetworkError):
            runtime.connect(BASE, parse(PROFILE))
        self.assertEqual(runtime.mode, 'blocked')
        self.assertIsNone(runtime.profile)
        self.assertTrue(all('masquerade' not in data for argv, data in runner.calls if argv[0] == 'nft' and data))

    def test_stale_handshake_not_connected(self):
        runtime = Runtime(NAMES, FakeRunner(), clock=lambda: 1500)
        runtime.connect(BASE, parse(PROFILE))
        self.assertFalse(runtime.handshake())

    def test_exit_check_is_bound_and_has_no_fallback(self):
        class ExitRunner(FakeRunner):
            def __call__(self, argv, data=None, optional=False):
                if argv[0] == 'curl':
                    self.calls.append((argv, data))
                    return subprocess.CompletedProcess(argv, 0, 'ip=203.0.113.9\nloc=IT\n')
                return super().__call__(argv, data, optional)
        runner = ExitRunner()
        runtime = Runtime(NAMES, runner, clock=lambda: 1010)
        runtime.connect(BASE, parse(PROFILE))
        self.assertEqual(runtime.verify_exit(), ('203.0.113.9', 'IT'))
        command = runner.calls[-1][0]
        self.assertEqual(command[command.index('--interface') + 1], 'phwg0')
        self.assertIn('--noproxy', command)
