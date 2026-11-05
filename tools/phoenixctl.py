#!/usr/bin/env python3
"""Local test client. Never changes host networking or prints credentials."""
import argparse
import json
import os
import secrets
import time
import urllib.request
from pathlib import Path


def request(base, token_file, path, body=None, content_type='application/json'):
    token = Path(token_file).read_text().strip()
    if len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('Invalid token file')
    # Fixed USB destination avoids forwarding the administrator token to arbitrary hosts.
    if base != 'http://192.168.7.1':
        raise ValueError('Only the dedicated USB management address is allowed')
    req = urllib.request.Request(base + '/api/v1/' + path, data=body,
                                 headers={'Authorization': 'Bearer ' + token,
                                          'Content-Type': content_type})
    # Ignore proxy environment variables: the bearer must remain on the local USB link.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=150) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token-file', default='results/admin.token')
    parser.add_argument('--base', default='http://192.168.7.1')
    commands = parser.add_subparsers(dest='command', required=True)
    pair = commands.add_parser('pair')
    pair.add_argument('--port', required=True)
    pair.add_argument('--reset', action='store_true')
    commands.add_parser('status')
    commands.add_parser('scan')
    uplink = commands.add_parser('uplink')
    uplink.add_argument('value', choices=['ethernet', 'wifi'])
    wifi = commands.add_parser('wifi')
    wifi.add_argument('value', choices=['sta', 'ap', 'saved'])
    wifi.add_argument('--ssid')
    wifi.add_argument('--save', action='store_true')
    mode = commands.add_parser('mode')
    mode.add_argument('value', choices=['blocked', 'direct'])
    vpn = commands.add_parser('vpn')
    vpn.add_argument('profile')
    firmware = commands.add_parser('firmware')
    firmware.add_argument('image')
    args = parser.parse_args()
    if args.command == 'pair':
        import serial
        from serial.tools import list_ports
        devices = [p for p in list_ports.comports() if p.device == args.port]
        if len(devices) != 1 or (devices[0].vid, devices[0].pid) != (0x1A86, 0x55D3):
            raise ValueError('Port is not the expected P4-NANO UART bridge')
        token = secrets.token_hex(32)
        target = Path(args.token_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(token + '\n')
        uart = serial.Serial(port=None, baudrate=115200, timeout=0.2)
        uart.dtr = False
        uart.rts = False
        uart.port = args.port
        with uart:
            if args.reset:
                uart.rts = True
                time.sleep(0.1)
                uart.rts = False
            # Opening some CH343 adapters can toggle reset; wait for the boot window.
            time.sleep(6)
            uart.reset_input_buffer()
            uart.write(f'time {int(time.time())}\npair {token}\n'.encode('ascii'))
            deadline = time.monotonic() + 5
            saved = False
            while time.monotonic() < deadline:
                if b'Pairing saved' in uart.readline():
                    saved = True
                    break
        if not saved:
            raise RuntimeError('No pairing acknowledgement; token file retained. Reboot and retry within 120 s using a new filename.')
        print('Pairing confirmed; token saved with mode 0600. Token not printed.')
    elif args.command == 'status':
        print(json.dumps(request(args.base, args.token_file, 'status'), indent=2))
    elif args.command == 'scan':
        print(json.dumps(request(args.base, args.token_file, 'wifi/scan'), indent=2))
    elif args.command == 'uplink':
        body = json.dumps({'uplink': args.value}).encode()
        print(json.dumps(request(args.base, args.token_file, 'uplink', body)))
    elif args.command == 'wifi':
        import getpass
        if args.value == 'saved':
            config = {'mode': 'sta', 'saved': True}
        else:
            if not args.ssid or not 1 <= len(args.ssid.encode()) <= 32:
                raise ValueError('SSID must contain 1..32 UTF-8 bytes')
            password = getpass.getpass('Wi-Fi password (not echoed): ')
            if not 8 <= len(password.encode()) <= 63:
                raise ValueError('Password must contain 8..63 bytes')
            config = {'mode': args.value, 'ssid': args.ssid, 'password': password}
            if args.save:
                if args.value != 'sta':
                    raise ValueError('Only STA credentials may be saved')
                config['save'] = True
        print(json.dumps(request(args.base, args.token_file, 'wifi', json.dumps(config).encode())))
    elif args.command == 'mode':
        body = json.dumps({'direct': args.value == 'direct'}).encode()
        print(json.dumps(request(args.base, args.token_file, 'mode', body)))
    elif args.command == 'firmware':
        body = Path(args.image).read_bytes()
        if not 4096 <= len(body) <= 6 * 1024 * 1024:
            raise ValueError('Signed image size must fit an OTA slot')
        print(json.dumps(request(args.base, args.token_file, 'firmware', body, 'application/octet-stream')))
    elif args.command == 'vpn':
        body = Path(args.profile).read_bytes()
        if not 0 < len(body) <= 4096:
            raise ValueError('Profile must contain 1..4096 bytes')
        print(json.dumps(request(args.base, args.token_file, 'vpn', body, 'text/plain')))


if __name__ == '__main__':
    main()
