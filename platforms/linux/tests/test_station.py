from pathlib import Path
import subprocess
import tempfile
import unittest
from phoenix_linux.station import Station, split_fields, validate
from phoenix_linux.runtime import NetworkError, Runtime
from test_policy import NAMES, BASE

BODY = {'mode': 'sta', 'ssid': 'Test:SSID', 'password': 'example-only-secret', 'save': True}


class StationTests(unittest.TestCase):
    def adapter(self, tmp, foreign=False, fail=False):
        self.commands = []
        def run(argv, **kwargs):
            self.commands.append(argv)
            out, code = '', 0
            if 'GENERAL.CON-UUID' in argv:
                out = 'foreign-uuid' if foreign else '--'
            if 'connection.id' in argv:
                code = 10
            if '--offline' in argv:
                out = '[connection]\nid=fixture\n'
            if 'passwd-file' in argv:
                text = Path(argv[-1]).read_text()
                self.assertIn(BODY['password'], text)
                if fail:
                    raise NetworkError('wifi_unavailable')
            if 'IP4.GATEWAY' in argv:
                out = '192.0.2.1\n'
            return subprocess.CompletedProcess(argv, code, out)
        return Station('wlan0', tmp, run)

    def test_secret_lifetime_persistence_and_no_argv_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            station = self.adapter(tmp)
            self.assertEqual(station.connect(BODY), '192.0.2.1')
            self.assertFalse((Path(tmp) / 'password').exists())
            self.assertNotIn(BODY['password'], str(self.commands))
            self.assertEqual(station.vault.load()['ssid'], BODY['ssid'])
            station.disconnect()
            self.assertFalse(station.active)

    def test_failure_removes_password_and_deactivates_owned_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            station = self.adapter(tmp, fail=True)
            with self.assertRaises(NetworkError):
                station.connect(BODY)
            self.assertFalse((Path(tmp) / 'password').exists())
            self.assertFalse(station.active)
            self.assertTrue(any('down' in cmd for cmd in self.commands))

    def test_foreign_connection_not_touched(self):
        with tempfile.TemporaryDirectory() as tmp:
            station = self.adapter(tmp, foreign=True)
            with self.assertRaises(NetworkError):
                station.connect(BODY)
            self.assertEqual(len(self.commands), 1)

    def test_validation_and_scan_escaping(self):
        self.assertEqual(split_fields(r'Name\:with\\slash:70:WPA2'), ['Name:with\\slash', '70', 'WPA2'])
        for change in ({'ssid': 'bad\nname'}, {'password': 'short'}, {'save': 1}):
            with self.assertRaises(ValueError):
                validate(dict(BODY, **change))

    def test_selected_uplink_uses_separate_route_table(self):
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            out = '[{"addr_info":[{"family":"inet","local":"192.0.2.10","prefixlen":24}]}]' if argv[:3] == ['ip', '-j', 'address'] else ''
            return subprocess.CompletedProcess(argv, 0, out)
        runtime = Runtime(NAMES, run)
        runtime.select_uplink(BASE, 'wlan1', 'wifi', '192.0.2.1')
        self.assertEqual(runtime.mode, 'blocked')
        self.assertEqual(runtime.names['uplink'], 'wlan1')
        self.assertTrue(any('17710' in cmd and 'fwmark' in cmd for cmd in calls))
        self.assertFalse(any('main' in cmd for cmd in calls))

    def test_startup_recovers_only_owned_station(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            station = Station('wlan0', tmp, lambda args, **kw: None)
            def run(args, **kwargs):
                calls.append(args)
                return SimpleNamespace(returncode=0, stdout=station.uuid if 'GENERAL.CON-UUID' in args else station.connection_name)
            station.run = run
            station.prepare_startup(restore_ap=True)
            self.assertIn(['nmcli', 'connection', 'down', 'uuid', station.uuid], calls)
            self.assertEqual(calls[-1], ['nmcli','device','set','wlan0','managed','no'])
            station.run = lambda args, **kw: SimpleNamespace(returncode=0, stdout='foreign')
            with self.assertRaises(NetworkError):
                station.prepare_startup(restore_ap=True)
