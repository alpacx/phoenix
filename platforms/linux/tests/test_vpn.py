import base64
import unittest
from phoenix_linux.wireguard import parse
from phoenix_linux.rotation import choose_country, Rotation

KEY = base64.b64encode(bytes(range(32))).decode()
PROFILE = f'[Interface]\nPrivateKey={KEY}\nAddress=10.5.0.2/32\nDNS=103.86.96.100\n[Peer]\nPublicKey={KEY}\nEndpoint=192.0.2.1:51820\nAllowedIPs=0.0.0.0/0\n'


class VpnTests(unittest.TestCase):
    def test_parse_and_no_secrets_in_repr(self):
        p = parse(PROFILE)
        self.assertEqual(p.mtu, 1380)
        self.assertNotIn('private_key', repr(p))
        self.assertNotIn('Address', p.setconf())
        self.assertIn('AllowedIPs = 0.0.0.0/0', p.setconf())

    def test_reject_scripts_duplicates_and_unsupported_profiles(self):
        for text in [PROFILE + 'PostUp=echo unsafe\n', PROFILE + 'PublicKey=' + KEY,
                     PROFILE.replace('192.0.2.1', 'example.com'),
                     PROFILE.replace('0.0.0.0/0', '::/0'),
                     PROFILE.replace('/32', '/0'),
                     PROFILE.replace('DNS=103.86.96.100\n', ''),
                     PROFILE + '[Peer]\n', PROFILE.replace('51820', '65536')]:
            with self.assertRaises(ValueError):
                parse(text)

    def test_fixed_country_and_exclusions(self):
        self.assertEqual(choose_country(['IT', 'US'], 'IT', 'IT'), 'IT')
        self.assertEqual(choose_country(['IT', 'US'], previous='IT'), 'US')
        self.assertEqual(choose_country(['IT', 'IQ'], exclude=True), 'IT')
        with self.assertRaises(ValueError):
            choose_country(['IT', 'IQ'], fixed='IQ', exclude=True)

    def test_monotonic_countdown_and_disconnect(self):
        now = [0]
        timer = Rotation(lambda: now[0])
        self.assertFalse(timer.due())
        timer.connected(True, 30)
        now[0] = 4.2
        self.assertEqual(timer.remaining(), 26)
        now[0] = 31
        self.assertTrue(timer.due())
        timer.disconnected()
        self.assertFalse(timer.due())
