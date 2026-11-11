import tempfile
import unittest
from phoenix_linux.nord import select, provision
from phoenix_linux.history import History
from phoenix_linux.store import ConfigStore
from test_vpn import KEY


class ProviderHistoryTests(unittest.TestCase):
    def test_wrong_country_and_offline_servers_rejected(self):
        server = {'status': 'online', 'id': 1, 'name': 'Test', 'station': '192.0.2.1',
                  'locations': [{'country': {'code': 'IT'}}],
                  'technologies': [{'identifier': 'wireguard_udp', 'metadata': [{'name': 'public_key', 'value': KEY}]}]}
        countries = [{'code': 'IT', 'id': 106}, {'code': 'US', 'id': 228}]
        p, info = select(KEY, countries, fixed='IT', request=lambda _: [server])
        self.assertEqual(info['country'], 'IT')
        with self.assertRaises(ValueError):
            select(KEY, countries, fixed='US', request=lambda _: [server])
        server['status'] = 'offline'
        with self.assertRaises(ValueError):
            select(KEY, countries, fixed='IT', request=lambda _: [server])

    def test_credentials_missing_key(self):
        with self.assertRaises(ValueError):
            provision('not-a-real-token', request=lambda *args: {})

    def test_history_expiry_pagination_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ConfigStore(tmp)
            now = [100000]
            history = History(store, clock=lambda: now[0])
            for i in range(55):
                history.add_confirmed('IT', 'Test', i)
            page = History(store, clock=lambda: now[0]).page()
            self.assertEqual(len(page['entries']), 50)
            self.assertEqual(len(history.page(page['next_before'])['entries']), 5)
            now[0] += 28801
            self.assertEqual(history.page()['entries'], [])
