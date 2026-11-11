import unittest
from phoenix_linux.access_point import render


class AccessPointTests(unittest.TestCase):
    def test_password_not_in_configuration_and_no_dns_proxy(self):
        result = render('wlan0', 'Phoenix-Test', 'test-password-only', 'IT', '103.86.96.100')
        self.assertNotIn('test-password-only', result['hostapd.conf'])
        self.assertIn('wpa_psk=', result['hostapd.conf'])
        self.assertIn('port=0', result['dnsmasq.conf'])
        self.assertIn('dhcp-option=6,103.86.96.100', result['dnsmasq.conf'])

    def test_injection_rejected_or_encoded(self):
        result = render('wlan0', 'Name\nconfig=bad', 'test-password-only', 'IT', '1.1.1.1')
        self.assertNotIn('config=bad', result['hostapd.conf'])
        with self.assertRaises(ValueError):
            render('wlan0\n', 'Name', 'test-password-only', 'IT', '1.1.1.1')
        with self.assertRaises(ValueError):
            render('wlan0', 'Name', 'test-password-only', 'IT\n', '1.1.1.1')
