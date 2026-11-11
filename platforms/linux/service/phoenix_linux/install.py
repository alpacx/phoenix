"""Explicit first installation on an identified target; never starts networking.

The initial bundle is trusted by the operator over SSH, not by its checksum.
Subsequent application releases require the separately provisioned public key.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import secrets
import subprocess
import zipfile
from .package import verify, DEPLOY
from .updates import crypto


def install(bundle, config, public_key=None, root=Path('/')):
    root = Path(root)
    target = json.loads(Path(config).read_text())
    model = (root / 'proc/device-tree/model').read_text().strip('\0\n')
    if not target.get('expected_model') or target['expected_model'] != model:
        raise ValueError('target_model_mismatch')
    verify(bundle)
    if public_key:
        der = crypto(['pkey', '-pubin', '-in', public_key, '-outform', 'DER'])
        if len(der) != 44 or der[:12] != bytes.fromhex('302a300506032b6570032100'):
            raise ValueError('ed25519_required')
        target['updates_config'] = '/etc/phoenix/updates.json'
    elif target.get('updates_config'):
        raise ValueError('trusted_key_required')
    destinations = ['opt/phoenix', 'opt/phoenix-releases', 'opt/phoenix-bootstrap', 'etc/phoenix']
    destinations += ['etc/systemd/system/' + name for name in DEPLOY if name.endswith('.service')]
    if any((root / p).exists() or (root / p).is_symlink() for p in destinations):
        raise ValueError('existing_installation_not_overwritten')
    release = root / 'opt/phoenix-releases/factory'
    release.mkdir(parents=True, mode=0o755)
    with zipfile.ZipFile(bundle) as archive:
        # Every path has been checked by the allowlist before creating files.
        archive.extractall(release)
    (root / 'opt/phoenix-releases').chmod(0o755)
    for path in [release, *release.rglob('*')]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    config_dir = root / 'etc/phoenix'
    config_dir.mkdir(parents=True, mode=0o700)
    target_path = config_dir / 'target.json'
    target_path.write_text(json.dumps(target, indent=2) + '\n')
    target_path.chmod(0o600)
    bootstrap = root / 'opt/phoenix-bootstrap/platforms/linux/service/phoenix_linux'
    bootstrap.mkdir(parents=True)
    for name in ('__init__.py', 'updates.py', 'package.py', 'vault.py'):
        shutil.copyfile(release / 'platforms/linux/service/phoenix_linux' / name, bootstrap / name)
    if public_key:
        key_path = config_dir / 'update-public.pem'
        shutil.copyfile(public_key, key_path)
        key_path.chmod(0o644)
        (config_dir / 'updates.json').write_text(json.dumps({'public_key': '/etc/phoenix/update-public.pem'}) + '\n')
        (config_dir / 'updates.json').chmod(0o600)
    unit_dir = root / 'etc/systemd/system'
    unit_dir.mkdir(parents=True, exist_ok=True)
    for name in DEPLOY:
        if name.endswith('.service'):
            shutil.copyfile(release / 'platforms/linux/deploy' / name, unit_dir / name)
    state = root / 'var/lib/phoenix'
    state.mkdir(parents=True, mode=0o700, exist_ok=True)
    token = state / 'admin-token'
    if not token.exists():
        token.write_text(secrets.token_hex(32))
        token.chmod(0o600)
    crypto(['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '365',
            '-subj', '/CN=Phoenix Local Administration',
            '-addext', 'subjectAltName=IP:127.0.0.1,DNS:localhost',
            '-keyout', config_dir / 'admin-key.pem', '-out', config_dir / 'admin-cert.pem'])
    (config_dir / 'admin-key.pem').chmod(0o600)
    (config_dir / 'admin-cert.pem').chmod(0o644)
    (root / 'opt/phoenix').symlink_to(release.resolve())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--target-config', required=True)
    parser.add_argument('--public-key')
    args = parser.parse_args()
    if os.geteuid() != 0 or not Path('/proc/sys/kernel').exists():
        raise SystemExit('Run only as root on the identified Linux target')
    import pwd
    try:
        pwd.getpwnam('phoenix-web')
    except KeyError:
        subprocess.run(['useradd', '--system', '--no-create-home', '--shell', '/usr/sbin/nologin', 'phoenix-web'], check=True)
    install(args.bundle, args.target_config, args.public_key)
    print('Installed; no service started and no network changed. Review target configuration before starting.')


if __name__ == '__main__':
    main()
