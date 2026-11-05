#!/usr/bin/env python3
"""Check signed package acceptance and tamper/wrong-key rejection using ESP-IDF espsecure."""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def run(*args):
    return subprocess.run([sys.executable, '-m', 'espsecure', *map(str, args)],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('key')
    args = parser.parse_args()
    def verify(image, key):
        return run('verify_signature', '--version', '2', '--keyfile', key, image).returncode == 0
    if not verify(args.image, args.key):
        raise RuntimeError('Original signature failed')
    with tempfile.TemporaryDirectory(prefix='phoenix-signature-') as folder:
        root = Path(folder)
        corrupted = bytearray(Path(args.image).read_bytes())
        corrupted[64] ^= 1
        bad_image = root / 'tampered.bin'
        bad_image.write_bytes(corrupted)
        if verify(bad_image, args.key):
            raise RuntimeError('Tampered image accepted')
        wrong_key = root / 'wrong.pem'
        generated = run('generate_signing_key', '--version', '2', '--scheme', 'rsa3072', wrong_key)
        if generated.returncode:
            raise RuntimeError('Test key generation failed')
        wrong_key.chmod(0o600)
        if verify(args.image, wrong_key):
            raise RuntimeError('Wrong key accepted')
    print('PASS: signed image accepted; tampered image and wrong key rejected (host only)')


if __name__ == '__main__':
    main()
