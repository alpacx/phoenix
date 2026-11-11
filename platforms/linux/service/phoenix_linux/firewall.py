"""Deterministic nftables compiler. No execution or global ruleset flush.

IPv4 only. This owns forwarding and must only be deployed on a dedicated
Phoenix target. INPUT management protections and DHCP/DNS provisioning are
separate and must be completed before exposing an administration listener.
"""
import re
from .policy import validate


def interface(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,14}', value):
        raise ValueError('invalid_interface')
    return value


def compile_rules(policy, interfaces, mode='blocked', existing=False):
    p = validate(policy)
    if mode not in ('blocked', 'vpn', 'direct'):
        raise ValueError('invalid_mode')
    names = {key: interface(interfaces[key]) for key in ('ap', 'usb', 'uplink', 'vpn')}
    if len(set(names.values())) != 4:
        raise ValueError('interfaces_must_be_distinct')
    lines = ['delete table inet phoenix'] if existing else []
    lines += ['table inet phoenix {', ' chain forward {',
              '  type filter hook forward priority -10; policy drop;',
              '  meta nfproto ipv6 counter drop', '  ct state invalid counter drop']
    if mode != 'blocked':
        exit_if = names['vpn' if mode == 'vpn' else 'uplink']
        for role, cidr in [('ap', '192.168.9.0/24'), ('usb', '192.168.7.0/24')]:
            src = names[role]
            lines += [f'  iifname "{src}" ip saddr != {cidr} counter drop',
                      f'  iifname "{exit_if}" oifname "{src}" ip daddr {cidr} ct state established,related counter accept']
            # Evaluate ordered rules for EVERY outgoing packet, including existing flows.
            for rule in p['rules']:
                if not rule['enabled'] or rule['ingress'] != role:
                    continue
                parts = [f'  iifname "{src}" oifname "{exit_if}"',
                         f'ip saddr {rule["source"]} ip daddr {rule["destination"]}']
                if rule['protocol']:
                    parts.append('ip protocol ' + str(rule['protocol']))
                if rule['port_first']:
                    proto = 'tcp' if rule['protocol'] == 6 else 'udp'
                    parts.append(f'{proto} dport {rule["port_first"]}-{rule["port_last"]}')
                parts.append('counter ' + ('accept' if rule['allow'] else 'drop'))
                lines.append(' '.join(parts))
            if p['default_allow']:
                lines.append(f'  iifname "{src}" oifname "{exit_if}" ip saddr {cidr} ip protocol {{ tcp, udp, icmp }} counter accept')
        for f in p['forwards']:
            if not f['enabled'] or f['vpn'] != (mode == 'vpn'):
                continue
            target = f['target'].split('/')[0]
            lan = names['ap' if target.startswith('192.168.9.') else 'usb']
            proto = 'tcp' if f['protocol'] == 6 else 'udp'
            lines.append(f'  iifname "{exit_if}" oifname "{lan}" ip saddr {f["source"]} ip daddr {target} {proto} dport {f["internal_port"]} ct status dnat counter accept')
            lines.append(f'  iifname "{lan}" oifname "{exit_if}" ip saddr {target} {proto} sport {f["internal_port"]} ct status dnat ct state established counter accept')
    lines.append('  counter drop')
    lines += [' }', ' chain prerouting {', '  type nat hook prerouting priority dstnat; policy accept;']
    if mode != 'blocked':
        for f in p['forwards']:
            if f['enabled'] and f['vpn'] == (mode == 'vpn'):
                proto = 'tcp' if f['protocol'] == 6 else 'udp'
                lines.append(f'  iifname "{exit_if}" ip saddr {f["source"]} {proto} dport {f["external_port"]} dnat ip to {f["target"].split("/")[0]}:{f["internal_port"]}')
    lines += [' }', ' chain postrouting {', '  type nat hook postrouting priority srcnat; policy accept;']
    if mode != 'blocked':
        lines.append(f'  oifname "{exit_if}" ip saddr {{ 192.168.7.0/24, 192.168.9.0/24 }} masquerade')
    lines += [' }', '}']
    return '\n'.join(lines) + '\n'
