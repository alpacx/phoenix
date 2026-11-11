"""API-compatible IPv4 policy validation; no shell interpolation."""
from copy import deepcopy
from ipaddress import IPv4Network


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid_integer')
    return value


def boolean(value):
    if type(value) is not bool:
        raise ValueError('invalid_boolean')
    return value


def network(value):
    if not isinstance(value, str):
        raise ValueError('invalid_cidr')
    return str(IPv4Network(value, strict=False))


def label(value):
    if not isinstance(value, str) or not 1 <= len(value.encode()) <= 32 or any(ord(c) < 32 for c in value):
        raise ValueError('invalid_label')


def validate(policy):
    if not isinstance(policy, dict):
        raise ValueError('invalid_policy')
    p = deepcopy(policy)
    integer(p['revision'], 0, 2**32 - 1)
    boolean(p['default_allow'])
    for key, limit in [('rules', 20), ('forwards', 8)]:
        if not isinstance(p[key], list) or len(p[key]) > limit:
            raise ValueError('too_many_rules')
    for rule in p['rules']:
        label(rule['name'])
        boolean(rule['enabled'])
        boolean(rule['allow'])
        if rule['ingress'] not in ('ap', 'usb'):
            raise ValueError('invalid_ingress')
        if integer(rule['protocol'], 0, 255) not in (0, 1, 6, 17):
            raise ValueError('invalid_protocol')
        for key in ('source', 'destination'):
            rule[key] = network(rule[key])
        first = integer(rule['port_first'], 0, 65535)
        last = integer(rule['port_last'], first, 65535)
        if (not first and last) or (last and rule['protocol'] not in (6, 17)):
            raise ValueError('invalid_port_range')
    seen = []
    for forward in p['forwards']:
        label(forward['name'])
        boolean(forward['enabled'])
        boolean(forward['vpn'])
        if integer(forward['protocol'], 0, 255) not in (6, 17):
            raise ValueError('invalid_protocol')
        external = integer(forward['external_port'], 1, 65535)
        integer(forward['internal_port'], 1, 65535)
        if external in (80, 51820) or 49152 <= external <= 61439:
            raise ValueError('reserved_port')
        target = IPv4Network(network(forward['target']))
        if target.prefixlen != 32 or not any(target.subnet_of(IPv4Network(n)) for n in ('192.168.7.0/24', '192.168.9.0/24')) or int(target.network_address) & 255 not in range(2, 255):
            raise ValueError('invalid_target')
        forward['target'] = str(target)
        forward['source'] = network(forward['source'])
        forward.pop('active', None)  # Runtime-only field echoed by current UI.
        for other in seen:
            if forward['enabled'] and other['enabled'] and forward['vpn'] == other['vpn'] and forward['protocol'] == other['protocol'] and (external == other['external_port'] or (forward['target'], forward['internal_port']) == (other['target'], other['internal_port'])):
                raise ValueError('duplicate_forward')
        seen.append(forward)
    return p
