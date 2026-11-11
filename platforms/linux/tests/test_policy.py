import copy
import unittest
from phoenix_linux.policy import validate
from phoenix_linux.firewall import compile_rules

NAMES = {'ap': 'wlan0', 'usb': 'usb0', 'uplink': 'end0', 'vpn': 'phwg0'}
BASE = {'revision': 0, 'default_allow': True, 'rules': [], 'forwards': []}


class PolicyTests(unittest.TestCase):
    def test_blocked_has_no_accept_or_nat(self):
        text = compile_rules(BASE, NAMES)
        self.assertNotIn('counter accept', text)
        self.assertNotIn('masquerade', text)
        self.assertIn('policy drop', text)

    def test_vpn_never_accepts_uplink(self):
        text = compile_rules(BASE, NAMES, 'vpn')
        self.assertNotIn('end0', text)
        self.assertIn('oifname "phwg0"', text)
        self.assertIn('meta nfproto ipv6 counter drop', text)

    def test_injection_and_aliases_rejected(self):
        for bad in ['eth0" accept', 'x;flush ruleset', 'wlan0']:
            with self.assertRaises(ValueError):
                compile_rules(BASE, dict(NAMES, uplink=bad))

    def test_rule_order_and_canonical_cidr(self):
        p = copy.deepcopy(BASE)
        rule = dict(name='Block', enabled=True, allow=False, ingress='ap',
                    protocol=6, source='192.168.9.19/24', destination='0.0.0.0/0',
                    port_first=443, port_last=443)
        p['rules'] = [rule]
        self.assertEqual(validate(p)['rules'][0]['source'], '192.168.9.0/24')
        text = compile_rules(p, NAMES, 'direct')
        self.assertLess(text.index('tcp dport 443-443 counter drop'), text.index('ip protocol { tcp, udp, icmp } counter accept'))
        self.assertEqual(rule['source'], '192.168.9.19/24')

    def test_forward_validation(self):
        p = copy.deepcopy(BASE)
        f = dict(name='Service', enabled=True, vpn=False, protocol=6,
                 external_port=8080, internal_port=443, source='0.0.0.0/0', target='192.168.9.2/32')
        p['forwards'] = [f]
        self.assertIn('dnat ip to 192.168.9.2:443', compile_rules(p, NAMES, 'direct'))
        self.assertNotIn('dnat ip to', compile_rules(p, NAMES, 'vpn'))
        for target in ['192.168.9.1', '192.168.9.255', '8.8.8.8', '192.168.9.2/24']:
            f['target'] = target
            with self.assertRaises(ValueError):
                validate(p)
        f['target'] = '192.168.9.2'
        for port in [80, 51820, 50000, True]:
            f['external_port'] = port
            with self.assertRaises(ValueError):
                validate(p)

    def test_duplicate_forwards(self):
        p = copy.deepcopy(BASE)
        f = dict(name='Service', enabled=True, vpn=True, protocol=17,
                 external_port=8080, internal_port=443, source='0.0.0.0/0', target='192.168.7.2')
        p['forwards'] = [f, copy.deepcopy(f)]
        with self.assertRaises(ValueError):
            validate(p)
