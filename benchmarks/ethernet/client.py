#!/usr/bin/env python3
"""Bounded TCP payload benchmark; requires the dedicated benchmark firmware."""
import argparse
import json
import socket
import struct
import time

p = argparse.ArgumentParser()
p.add_argument('host')
p.add_argument('--trials', type=int, default=3)
a = p.parse_args()
size = 32 * 1024 * 1024
block = bytes(8192)
for trial in range(a.trials):
    for direction in ('U', 'D'):
        with socket.create_connection((a.host, 5001), timeout=10) as s:
            s.settimeout(10)
            s.sendall(direction.encode())
            start = time.monotonic()
            total = 0
            while total < size:
                if time.monotonic() - start > 60:
                    raise TimeoutError('Run exceeded 60 seconds')
                if direction == 'U':
                    s.sendall(block)
                    total += len(block)
                else:
                    data = s.recv(min(65536, size-total))
                    if not data:
                        raise RuntimeError(f'Truncated transfer: {total}/{size}')
                    total += len(data)
            if direction == 'U':
                ack = b''
                while len(ack) < 4:
                    data = s.recv(4-len(ack))
                    if not data:
                        raise RuntimeError('Missing receiver acknowledgement')
                    ack += data
                if struct.unpack('!I', ack)[0] != size:
                    raise RuntimeError('Receiver byte count mismatch')
            elapsed = time.monotonic()-start
            print(json.dumps(dict(trial=trial+1, direction=direction,
                  bytes=total, seconds=elapsed, mbps=total*8/elapsed/1e6)), flush=True)
        time.sleep(1)
