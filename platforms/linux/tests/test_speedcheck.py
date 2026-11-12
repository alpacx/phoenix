import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from phoenix_linux.speedcheck import Measurement, sanitize
from phoenix_linux.controller import Controller
from phoenix_linux.store import RevisionConflict


class SpeedcheckTests(unittest.TestCase):
    def test_result_conversion_and_no_client_metadata(self):
        value = sanitize([(28, '100000000 10.0 200')] * 4, 10)
        self.assertEqual(value['download_mbps'], 320)
        self.assertEqual(value['download_mb'], 400)
        self.assertIsNone(value['upload_mbps'])
        self.assertIsNone(value['ping_ms'])
        for bad in ['nan 10 200', 'inf 10 200', '-1 10 200', '1 10 302', '1 10 500', '1 0.1 200']:
            with self.assertRaises(ValueError):
                sanitize([(28, bad)] * 4, 10)
        with self.assertRaises(ValueError):
            sanitize([(7, '1000 10 200')] * 4, 10)
        with self.assertRaises(ValueError):
            sanitize([(28, '1000 10 200')], 10)

    def test_cooldown_and_interface_validation(self):
        m = Measurement()
        with self.assertRaises(ValueError):
            m.prepare('vpn', '../eth0', '')
        m.prepare('vpn', 'phwg0', 'Example')
        with self.assertRaises(ValueError):
            m.prepare('vpn', 'phwg0', 'Example')
        self.assertEqual(m.status()['mode'], 'vpn')

    def test_running_test_rejects_other_commands_and_never_changes_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = Controller(tmp, [])
            c.runtime = SimpleNamespace(mode='blocked', names={'vpn':'phwg0','uplink':'eth0'}, handshake=lambda: True)
            with patch('phoenix_linux.speedcheck.available', return_value=True):
                with self.assertRaises(ValueError):
                    c.start_speedtest()
                c.runtime.mode = 'vpn'
                entered, finish = threading.Event(), threading.Event()
                def run(name):
                    self.assertEqual(name, 'phwg0')
                    entered.set(); finish.wait(3)
                c.measurement.run = run
                c.start_speedtest()
                self.assertTrue(entered.wait(2))
                with self.assertRaises(RevisionConflict):
                    c.submit({'action': 'direct'})
                self.assertEqual(c.runtime.mode, 'vpn')
                finish.set()
                for _ in range(30):
                    if not c.busy: break
                    time.sleep(.01)
                self.assertFalse(c.busy)

    def test_thermal_limit_terminates_worker(self):
        m=Measurement();m.prepare('vpn','phwg0','')
        process=SimpleNamespace(poll=lambda: None,terminate=lambda: calls.append('terminate'),wait=lambda timeout: None)
        calls=[]
        with patch('phoenix_linux.speedcheck.subprocess.Popen',return_value=process),patch('phoenix_linux.speedcheck.temperatures',return_value=[76]),patch('phoenix_linux.speedcheck.Path.exists',return_value=True),patch('phoenix_linux.speedcheck.shutil.which',return_value='/usr/bin/curl'):
            m.run('phwg0')
        self.assertEqual(m.status()['error'],'temperature_limit')
        self.assertEqual(calls,[])  # Too hot: do not start any transfer.

    def test_cancel_stops_all_native_transfers_and_binds_interface(self):
        m=Measurement();m.prepare('vpn','phwg0','')
        processes=[];commands=[]
        class Process:
            returncode=None
            def poll(self): return self.returncode
            def terminate(self): self.returncode=-15
            def wait(self,timeout): return self.returncode
        def launch(args,**kwargs):
            commands.append(args);p=Process();processes.append(p)
            if len(processes)==4:m.cancel()
            return p
        with patch('phoenix_linux.speedcheck.Path.exists',return_value=True),patch('phoenix_linux.speedcheck.shutil.which',return_value='/usr/bin/curl'),patch('phoenix_linux.speedcheck.temperatures',return_value=[50]),patch('phoenix_linux.speedcheck.subprocess.Popen',side_effect=launch):
            m.run('phwg0')
        self.assertEqual(m.status()['state'],'cancelled')
        self.assertEqual(len(processes),4)
        self.assertTrue(all(p.returncode==-15 for p in processes))
        self.assertTrue(all(c[1]=='--disable' and 'if!phwg0' in c and '--noproxy' in c for c in commands))
