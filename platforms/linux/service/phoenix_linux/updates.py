"""Signed application releases, monotonic sequence, atomic activation and rollback.

Does not update the kernel, bootloader, systemd units or trusted bootstrap.
Trusted public key is provisioned separately; uploaded keys are never trusted.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import stat
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from .package import verify as verify_payload
from .vault import Vault

MAX_UPLOAD = 20 * 1024 * 1024


def crypto(args):
    result = subprocess.run(['openssl', *map(str, args)], capture_output=True, timeout=15)
    if result.returncode:
        raise ValueError('signature_operation_failed')
    return result.stdout


def legacy_ed25519():
    # OpenSSL 1.1.1 supports Ed25519 through EVP, but not pkeyutl -rawin.
    # Select before verification; never retry a failed signature with a fallback.
    return crypto(['version']).startswith(b'OpenSSL 1.1.1')


def legacy_sign(key, message):
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private = load_pem_private_key(Path(key).read_bytes(), password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError('ed25519_required')
    return private.sign(message)


def legacy_verify(der, signature, message):
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    public = load_der_public_key(der)
    if not isinstance(public, Ed25519PublicKey):
        raise ValueError('ed25519_required')
    try:
        public.verify(signature, message)
    except InvalidSignature:
        raise ValueError('signature_operation_failed') from None


def sign(payload, output, key, sequence, version):
    if type(sequence) is not int or not 1 <= sequence < 2**53 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', version):
        raise ValueError('invalid_release_metadata')
    verify_payload(payload)
    data = Path(payload).read_bytes()
    meta = json.dumps({'kind': 'phoenix-linux-application', 'format': 1, 'sequence': sequence,
                       'version': version, 'sha256': hashlib.sha256(data).hexdigest()}, sort_keys=True, separators=(',', ':')).encode()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'metadata'
        path.write_bytes(meta)
        signature = (legacy_sign(key, meta) if legacy_ed25519() else
                     crypto(['pkeyutl', '-sign', '-rawin', '-inkey', key, '-in', path]))
    if len(signature) != 64:
        raise ValueError('ed25519_required')
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('release.json', meta)
        archive.writestr('payload.zip', data)
        archive.writestr('signature.bin', signature)


def verify(data, public_key):
    if not isinstance(data, bytes) or len(data) > MAX_UPLOAD:
        raise ValueError('update_too_large')
    public_key = Path(public_key)
    if public_key.is_symlink() or public_key.stat().st_uid != os.getuid() or public_key.stat().st_mode & 0o022:
        raise ValueError('untrusted_key_file_permissions')
    der = crypto(['pkey', '-pubin', '-in', public_key, '-outform', 'DER'])
    if len(der) != 44 or der[:12] != bytes.fromhex('302a300506032b6570032100'):
        raise ValueError('ed25519_required')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) != 3 or {e.filename for e in entries} != {'release.json', 'payload.zip', 'signature.bin'}:
            raise ValueError('invalid_update_archive')
        if sum(e.file_size for e in entries) > MAX_UPLOAD or any(stat.S_ISLNK(e.external_attr >> 16) for e in entries):
            raise ValueError('invalid_update_archive')
        meta, payload, signature = (archive.read(n) for n in ('release.json', 'payload.zip', 'signature.bin'))
    if len(meta) > 4096 or len(signature) != 64:
        raise ValueError('invalid_signature')
    with tempfile.TemporaryDirectory() as tmp:
        path, sig = Path(tmp) / 'metadata', Path(tmp) / 'signature'
        path.write_bytes(meta)
        sig.write_bytes(signature)
        if legacy_ed25519():
            legacy_verify(der, signature, meta)
        else:
            crypto(['pkeyutl', '-verify', '-pubin', '-rawin', '-inkey', public_key, '-in', path, '-sigfile', sig])
        inner = Path(tmp) / 'payload.zip'
        inner.write_bytes(payload)
        verify_payload(inner)
    release = json.loads(meta)
    if release.get('kind') != 'phoenix-linux-application' or release.get('format') != 1:
        raise ValueError('wrong_update_type')
    if type(release.get('sequence')) is not int or not 1 <= release['sequence'] < 2**53:
        raise ValueError('invalid_sequence')
    if not isinstance(release.get('version'), str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', release['version']):
        raise ValueError('invalid_version')
    if hashlib.sha256(payload).hexdigest() != release.get('sha256'):
        raise ValueError('payload_hash_mismatch')
    return release, payload


class Updates:
    def __init__(self, releases, current, state, public_key):
        self.releases, self.current = Path(releases), Path(current)
        self.state_dir, self.public_key = Path(state), Path(public_key)
        for directory in (self.releases, self.state_dir):
            directory.mkdir(parents=True, mode=0o700, exist_ok=True)
            if directory.is_symlink() or directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o022:
                raise ValueError('update_directory_permissions')
        self.vault = Vault(self.state_dir)
        self.vault.path = self.state_dir / 'update-state.json'

    @contextmanager
    def locked(self):
        fd = os.open(self.state_dir / 'update.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def status(self):
        state = self.vault.load()
        return {key: state.get(key) for key in ('phase', 'version', 'max_sequence', 'error')}

    def check_current(self):
        if not self.current.is_symlink():
            raise ValueError('current_must_be_managed_release_symlink')
        target = self.current.resolve(strict=True)
        if target.parent != self.releases.resolve():
            raise ValueError('current_outside_release_directory')
        return target.name

    def switch(self, name):
        if name in ('.', '..') or not re.fullmatch(r'[A-Za-z0-9._-]+', name):
            raise ValueError('invalid_release_name')
        target = self.releases / name
        if target.is_symlink() or not target.is_dir():
            raise ValueError('release_missing')
        temporary = self.current.with_name(self.current.name + '.switch')
        if temporary.is_symlink():
            temporary.unlink()  # Interrupted atomic switch in this root-owned directory.
        elif temporary.exists():
            raise ValueError('switch_path_already_exists')
        temporary.symlink_to(target.resolve())
        os.replace(temporary, self.current)
        fd = os.open(self.current.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def stage(self, data):
        release, payload = verify(data, self.public_key)
        with self.locked():
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                needed = sum(item.file_size for item in archive.infolist()) + 64 * 1024 * 1024
            if shutil.disk_usage(self.releases).free < needed:
                raise ValueError('insufficient_update_space')
            previous = self.check_current()
            state = self.vault.load()
            if state.get('phase') in ('staged', 'activating'):
                raise ValueError('update_in_progress')
            if release['sequence'] <= state.get('max_sequence', 0):
                raise ValueError('update_replay_or_downgrade')
            name = str(release['sequence']) + '-' + release['sha256'][:16]
            destination = self.releases / name
            if destination.exists():
                raise ValueError('release_already_exists')
            staging = Path(tempfile.mkdtemp(prefix='.stage-', dir=self.releases))
            try:
                with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                    for item in archive.infolist():
                        path = staging / item.filename  # Already allowlisted by verify_payload.
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with path.open('xb') as stream:
                            stream.write(archive.read(item))
                            stream.flush()
                            os.fsync(stream.fileno())
                        path.chmod(0o644)
                for directory in sorted((p for p in staging.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True) + [staging]:
                    directory.chmod(0o755)
                    fd = os.open(directory, os.O_RDONLY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                os.replace(staging, destination)
                fd = os.open(self.releases, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
                self.vault.save({'phase': 'staged', 'max_sequence': release['sequence'],
                                 'version': release['version'], 'previous': previous, 'next': name, 'error': ''})
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
            return self.status()

    def recover(self):
        with self.locked():
            state = self.vault.load()
            if state.get('phase') != 'activating':
                return False
            self.switch(state['previous'])
            state.update(phase='rolled_back', error='interrupted_update')
            self.vault.save(state)
            return True

    def activate(self, service, healthy):
        with self.locked():
            state = self.vault.load()
            if state.get('phase') != 'staged':
                raise ValueError('no_staged_update')
            if self.check_current() != state['previous']:
                raise ValueError('current_release_changed')
            state.update(phase='activating')
            self.vault.save(state)
            try:
                service('stop')
                self.switch(state['next'])
                service('start')
                if not healthy(state['next']):
                    raise ValueError('updated_service_unhealthy')
                state.update(phase='active', error='')
                self.vault.save(state)
            except Exception:
                try:
                    service('stop')
                    self.switch(state['previous'])
                    service('start')
                    state.update(phase='rolled_back', error='activation_failed')
                except Exception:
                    state.update(phase='rollback_failed', error='manual_recovery_required')
                self.vault.save(state)
                raise ValueError(state['error']) from None
            return self.status()


def from_config(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o022:
        raise ValueError('untrusted_update_configuration')
    config = json.loads(path.read_text())
    return Updates('/opt/phoenix-releases', '/opt/phoenix', '/var/lib/phoenix', config['public_key'])


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    signer = sub.add_parser('sign')
    for arg in ('payload', 'output', 'key', 'version'):
        signer.add_argument('--' + arg, required=True)
    signer.add_argument('--sequence', type=int, required=True)
    for action in ('activate', 'recover'):
        command = sub.add_parser(action)
        command.add_argument('--config', default='/etc/phoenix/updates.json')
        if action == 'recover':
            command.add_argument('--restart', action='store_true')
    args = parser.parse_args()
    if args.action == 'sign':
        sign(args.payload, args.output, args.key, args.sequence, args.version)
        print('Signed application release created')
        return
    if os.geteuid() != 0 or not Path('/proc/sys/kernel').exists():
        raise SystemExit('Linux root required')
    updater = from_config(args.config)
    def service(action):
        if action == 'restart':
            service('stop')
            service('start')
            return
        units = ('phoenix.service', 'phoenix-control.service') if action == 'stop' else ('phoenix-control.service', 'phoenix.service')
        for unit in units:
            subprocess.run(['systemctl', action, unit], check=True, capture_output=True, timeout=120)
    if args.action == 'recover':
        if updater.recover() and args.restart:
            service('restart')
        return
    def healthy(name):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile='/etc/phoenix/admin-cert.pem')))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                with opener.open('https://127.0.0.1:8443/healthz', timeout=2) as response:
                    status = json.loads(response.read(4096))
                    if status.get('ready') is True and status.get('release_id') == name:
                        return True
            except Exception:
                pass
            time.sleep(1)
        return False
    updater.activate(service, healthy)


if __name__ == '__main__':
    main()
