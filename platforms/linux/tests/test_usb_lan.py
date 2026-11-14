import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from phoenix_linux.usb_lan import UsbLan
from phoenix_linux.runtime import NetworkError
from test_lan import Process


class UsbLanTests(unittest.TestCase):
    def make(self, directory, bound=True, managed='no', addresses=None, routes=None, fail=False):
        self.commands, self.processes = [], []
        def run(argv, **kwargs):
            self.commands.append(argv)
            out = managed if argv[0] == 'nmcli' else ''
            if argv[:3] == ['ip', '-j', 'address']:out = json.dumps(addresses or [])
            if argv[:4] == ['ip', '-j', '-4', 'route']:out = json.dumps(routes or [])
            return subprocess.CompletedProcess(argv, 0, out)
        def popen(argv, **kwargs):
            if fail:raise OSError('failed daemon')
            self.assertEqual(argv[0], 'dnsmasq')
            proc = Process(); self.processes.append(proc); return proc
        return UsbLan('phusb0', '1.1.1.1', directory, run, popen=popen,
                      which=lambda _: '/tool', wait=lambda _: None, binding=lambda _: bound)

    def test_dhcp_usb_subnet_dns_update_and_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            usb = self.make(tmp); usb.start(); self.assertTrue(usb.healthy())
            text = (Path(tmp) / 'dnsmasq.conf').read_text()
            self.assertIn('dhcp-option=3,192.168.7.1', text)
            self.assertIn('port=0', text)
            self.assertFalse((Path(tmp) / 'hostapd.conf').exists())
            first = self.processes[0]; usb.set_dns('9.9.9.9'); self.assertTrue(first.stopped)
            self.assertIn('dhcp-option=6,9.9.9.9', (Path(tmp) / 'dnsmasq.conf').read_text())
            usb.stop(); self.assertFalse(usb.healthy())
            self.assertIn(['ip','address','del','192.168.7.1/24','dev','phusb0'], self.commands)

    def test_conflicts_block_before_address_changes(self):
        for options in ({'bound':False}, {'managed':'yes'}, {'routes':[{'dst':'192.168.7.0/24','dev':'eth0'}]},
                        {'addresses':[{'addr_info':[{'family':'inet','local':'10.0.0.1','prefixlen':24}]}]}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as tmp:
                usb = self.make(tmp, **options)
                with self.assertRaises(NetworkError):usb.start()
                self.assertFalse(any(c[:3] == ['ip','address','add'] for c in self.commands))

    def test_partial_start_removes_only_added_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            usb = self.make(tmp, fail=True)
            with self.assertRaises(OSError):usb.start()
            self.assertFalse(usb.active)
            self.assertIn(['ip','address','del','192.168.7.1/24','dev','phusb0'], self.commands)

    def test_gadget_unbinding_is_unhealthy_but_cable_carrier_not_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            usb = self.make(tmp); usb.start(); self.assertTrue(usb.healthy())
            usb.binding = lambda _: False
            self.assertFalse(usb.healthy()); usb.stop()

class UsbControllerTests(unittest.TestCase):
    def test_dns_tracks_vpn_and_dhcp_failure_blocks_forwarding(self):
        from unittest.mock import Mock
        from phoenix_linux.controller import Controller
        from phoenix_linux.runtime import Runtime
        from test_runtime import FakeRunner
        from test_policy import NAMES
        from test_vpn import PROFILE
        from phoenix_linux.wireguard import parse
        with tempfile.TemporaryDirectory() as tmp:
            controller = Controller(tmp, [], Runtime(NAMES, FakeRunner(), clock=lambda: 1010))
            controller.usb_lan = Mock(default_dns='1.1.1.1')
            controller.usb_lan.healthy.return_value = True
            controller.command({'action':'wireguard', 'profile':PROFILE})
            controller.usb_lan.set_dns.assert_called_with(parse(PROFILE).dns)
            controller.usb_lan.healthy.return_value = False
            controller.tick()
            self.assertEqual(controller.runtime.mode, 'blocked')
            self.assertEqual(controller.error, 'usb_dhcp_service_failed')
            controller.usb_lan.healthy.return_value = True
            controller.command({'action':'direct'})
            controller.usb_lan.set_dns.assert_called_with('1.1.1.1')
