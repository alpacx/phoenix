"""Generate private hostapd/DHCP configuration; never changes networking itself.

Driver AP support, regulatory domain, NetworkManager ownership and interface
assignment must be checked on the target before installing these files.
"""
import hashlib
import re
from ipaddress import IPv4Address
from .firewall import interface


def render(name, ssid, password, country, dns):
    name = interface(name)
    if not isinstance(ssid, str) or not 1 <= len(ssid.encode('utf8')) <= 32:
        raise ValueError('invalid_ssid')
    if not isinstance(password, str) or not 8 <= len(password) <= 63 or not password.isascii() or any(ord(c) < 32 for c in password):
        raise ValueError('invalid_wifi_password')
    if not isinstance(country, str) or not re.fullmatch('[A-Z]{2}', country):
        raise ValueError('invalid_regulatory_country')
    dns = str(IPv4Address(dns))
    psk = hashlib.pbkdf2_hmac('sha1', password.encode(), ssid.encode(), 4096, 32).hex()
    hostapd = f'''interface={name}
driver=nl80211
ssid2={ssid.encode().hex()}
country_code={country}
ieee80211d=1
hw_mode=g
channel=6
wmm_enabled=1
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_psk={psk}
'''
    # DHCP only. Client DNS is routed through the same firewall/tunnel as other traffic.
    dhcp = f'''port=0
interface={name}
bind-interfaces
dhcp-range=192.168.9.20,192.168.9.200,255.255.255.0,1h
dhcp-option=3,192.168.9.1
dhcp-option=6,{dns}
dhcp-authoritative
'''
    return {'hostapd.conf': hostapd, 'dnsmasq.conf': dhcp}
