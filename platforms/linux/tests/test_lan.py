from pathlib import Path
import subprocess
import tempfile
import unittest
from phoenix_linux.lan import AccessPoint
from phoenix_linux.runtime import NetworkError


class Process:
    def __init__(self):
        self.stopped = False
    def poll(self):
        return 0 if self.stopped else None
    def terminate(self):
        self.stopped = True
    def wait(self, timeout):
        return 0


class LanTests(unittest.TestCase):
    def manager(self, directory, managed='no', addresses='[]', fail_dns=False):
        self.commands, self.processes = [], []
        def run(argv, **kwargs):
            self.commands.append(argv)
            out = managed if argv[0] == 'nmcli' else ''
            if argv[:3] == ['iw', 'dev', 'wlan0']:
                out = 'Interface wlan0\n wiphy 0\n'
            if argv[:3] == ['iw', 'phy', 'phy0']:
                out = 'Supported interface modes:\n * managed\n * AP\n'
            if argv[:3] == ['ip', '-j', 'address']:
                out = addresses
            return subprocess.CompletedProcess(argv, 0, out)
        def popen(argv, **kwargs):
            if argv[0] == 'dnsmasq' and fail_dns:
                raise OSError('startup_failed')
            process = Process()
            self.processes.append(process)
            return process
        return AccessPoint('wlan0', 'Phoenix-Test', 'test-password-only', 'IT', '1.1.1.1',
                           directory, run, popen=popen, which=lambda _: '/bin/tool', wait=lambda _: None)

    def test_ownership_conflict_has_no_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            ap = self.manager(tmp, managed='yes')
            with self.assertRaises(NetworkError):
                ap.start()
            self.assertEqual(len(self.commands), 1)
            self.assertFalse(list(Path(tmp).iterdir()))

    def test_existing_address_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            ap = self.manager(tmp, addresses='[{"addr_info":[{"family":"inet","local":"10.0.0.2","prefixlen":24}]}]')
            with self.assertRaises(NetworkError):
                ap.start()
            self.assertFalse(any('add' in cmd for cmd in self.commands))

    def test_owned_processes_stop_and_secrets_not_in_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            ap = self.manager(tmp)
            ap.start()
            self.assertTrue(ap.healthy())
            self.assertEqual((Path(tmp) / 'hostapd.conf').stat().st_mode & 0o777, 0o600)
            self.assertNotIn('test-password-only', str(self.commands))
            ap.stop()
            self.assertTrue(all(p.stopped for p in self.processes))
            self.assertTrue(any(cmd[:3] == ['ip', 'address', 'del'] for cmd in self.commands))

    def test_partial_start_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            ap = self.manager(tmp, fail_dns=True)
            with self.assertRaises(OSError):
                ap.start()
            self.assertFalse(ap.active)
            self.assertTrue(all(p.stopped for p in self.processes))

    def test_dns_change_keeps_ap_and_restarts_only_dhcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            ap = self.manager(tmp)
            ap.start()
            hostapd, dns = ap.processes
            ap.set_dns('9.9.9.9')
            self.assertFalse(hostapd.stopped)
            self.assertTrue(dns.stopped)
            self.assertTrue(ap.healthy())
            self.assertIn('dhcp-option=6,9.9.9.9', (Path(tmp) / 'dnsmasq.conf').read_text())
            ap.stop()
