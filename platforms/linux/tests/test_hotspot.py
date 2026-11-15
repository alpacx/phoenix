from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from phoenix_linux.controller import Controller
from phoenix_linux.store import RevisionConflict
import test_lan

class HotspotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.c=Controller(self.tmp.name,[])
        self.fixture=test_lan.LanTests()
        self.ap=self.fixture.manager(Path(self.tmp.name)/'ap')
        self.c.access_point=self.ap
        self.ap.start()
    def tearDown(self):
        self.ap.stop();self.tmp.cleanup()
    def test_save_disable_enable_and_secret_not_exposed(self):
        value=self.c.configure_hotspot({'enabled':False,'ssid':'Personal WiFi','password':'new-test-password'})
        self.assertFalse(value['enabled']);self.assertFalse(self.ap.active)
        self.assertNotIn('password',value)
        self.assertEqual(self.c.hotspot_vault.load()['password'],'new-test-password')
        self.c.configure_hotspot({'enabled':True,'ssid':'Personal WiFi','password':''})
        self.assertTrue(self.ap.active)
        self.assertEqual(self.ap.password,'new-test-password')
    def test_reject_invalid_and_station_conflict_before_mutations(self):
        for body in [{'enabled':1,'ssid':'x'}, {'enabled':True,'ssid':'x'*33}, {'enabled':True,'ssid':'x','password':'short'}]:
            with self.assertRaises(ValueError):self.c.configure_hotspot(body)
            self.assertTrue(self.ap.active)
        self.c.ap_suspended=True
        with self.assertRaises(ValueError):self.c.configure_hotspot({'enabled':True,'ssid':'x'})
    def test_failed_save_restores_previous_live_configuration(self):
        with patch.object(self.c.hotspot_vault,'save',side_effect=OSError('disk')):
            with self.assertRaises(OSError):self.c.configure_hotspot({'enabled':False,'ssid':'changed'})
        self.assertTrue(self.ap.active);self.assertEqual(self.ap.ssid,'Phoenix-Test')
    def test_busy_and_no_false_radio_confirmation(self):
        self.assertFalse(self.c.hotspot_status()['active'])
        with patch.object(self.ap,'radio_status',return_value={'state':'ENABLED','clients':2}):
            self.assertTrue(self.c.hotspot_status()['active'])
        self.c.busy=True
        with self.assertRaises(RevisionConflict):self.c.configure_hotspot({'enabled':False,'ssid':'x'})
