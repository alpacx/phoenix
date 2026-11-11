"""Nord provisioning/catalog adapter, same API flow as ESP32.

Token is used for a single HTTPS request, not persisted. Python cannot promise
zeroization of immutable strings. Redirects and environment proxies disabled.
"""
import base64
import json
import secrets
import urllib.request
import urllib.parse
from .rotation import choose_country
from .wireguard import key, parse


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get(path, token=None, transport=None):
    if not path.startswith('/v1/'):
        raise ValueError('invalid_api_path')
    headers = {'Accept': 'application/json'}
    if token:
        if not isinstance(token, str) or not 1 <= len(token) <= 512 or any(ord(c) < 33 for c in token):
            raise ValueError('invalid_token')
        headers['Authorization'] = 'Basic ' + base64.b64encode(('token:' + token).encode()).decode()
    if transport is not None:
        try:
            return transport(path, headers)
        except Exception:
            raise ValueError('nord_api_failed') from None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(urllib.request.Request('https://api.nordvpn.com' + path, headers=headers), timeout=12) as response:
            if response.status != 200:
                raise ValueError('nord_api_failed')
            body = response.read(262145)
            if len(body) > 262144:
                raise ValueError('nord_response_too_large')
            return json.loads(body)
    except Exception:
        raise ValueError('nord_api_failed') from None


def provision(token, request=get):
    result = request('/v1/users/services/credentials', token)
    return key(result.get('nordlynx_private_key', ''))


def select(private_key, countries, fixed='', previous='', exclude=False,
           previous_server=0, request=get, choice=secrets.choice):
    private_key = key(private_key)
    ids = {c['code']: c['id'] for c in countries}
    country = choose_country(ids, fixed, previous, exclude, choice)
    query = urllib.parse.urlencode({'filters[servers_technologies][identifier]': 'wireguard_udp',
                                    'filters[country_id]': ids[country], 'limit': 5})
    result = request('/v1/servers/recommendations?' + query)
    if not isinstance(result, list):
        raise ValueError('invalid_catalog')
    candidates = []
    for server in result[:5]:
        try:
            if server['status'] != 'online' or server['locations'][0]['country']['code'] != country:
                continue
            pub = next(m['value'] for t in server['technologies'] if t['identifier'] == 'wireguard_udp'
                       for m in t['metadata'] if m['name'] == 'public_key')
            if type(server['id']) is not int or server['id'] <= 0:
                continue
            profile = parse(f'[Interface]\nPrivateKey={private_key}\nAddress=10.5.0.2/32\nDNS=103.86.96.100\nMTU=1380\n[Peer]\nPublicKey={pub}\nEndpoint={server["station"]}:51820\nAllowedIPs=0.0.0.0/0\nPersistentKeepalive=25\n')
            candidates.append((profile, {'id': server['id'], 'country': country, 'server': str(server['name'])[:63]}))
        except (KeyError, ValueError, TypeError, IndexError, StopIteration):
            continue
    alternatives = [c for c in candidates if c[1]['id'] != previous_server]
    if not candidates:
        raise ValueError('no_server_in_selected_country')
    return choice(alternatives or candidates)
