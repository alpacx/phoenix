"""Build and verify an allowlisted deployment bundle; no network or installation.

SHA-256 detects corruption, not publisher authenticity. This is not signed OTA.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[4]
ASSETS = ('index.html', 'app.js', 'app.css', 'countries.json')
DEPLOY = ('phoenix.service', 'phoenix-control.service', 'phoenix-update.service', 'phoenix-update-recover.service', 'target.example.json')


def permitted(name):
    path = PurePosixPath(name)
    if str(path) != name or '..' in path.parts or path.is_absolute():
        return False
    return ((path.parent == PurePosixPath('platforms/linux/service/phoenix_linux') and path.suffix == '.py')
            or name in ('platforms/linux/deploy/' + filename for filename in DEPLOY)
            or name in ('shared/web/' + asset for asset in ASSETS))


def build(output, root=ROOT):
    root, output = Path(root), Path(output)
    files = list((root / 'platforms/linux/service/phoenix_linux').glob('*.py'))
    files += [root / 'shared/web' / name for name in ASSETS]
    files += [root / 'platforms/linux/deploy' / name for name in DEPLOY]
    contents = {}
    for path in sorted(files):
        name = path.relative_to(root).as_posix()
        if path.is_symlink() or not permitted(name):
            raise ValueError('unexpected_package_source')
        contents[name] = path.read_bytes()
    manifest = {'format': 1, 'signed': False, 'files': {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}}
    contents['manifest.json'] = json.dumps(manifest, sort_keys=True, indent=2).encode()
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    verify(output)
    return manifest


def verify(bundle):
    with zipfile.ZipFile(bundle) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or len(names) > 128 or sum(e.file_size for e in entries) > 16 * 1024 * 1024:
            raise ValueError('invalid_archive_size_or_duplicates')
        for entry in entries:
            if entry.filename != 'manifest.json' and not permitted(entry.filename):
                raise ValueError('unexpected_archive_path')
            if stat.S_ISLNK(entry.external_attr >> 16) or entry.is_dir():
                raise ValueError('archive_links_not_allowed')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 1 or manifest.get('signed') is not False:
            raise ValueError('unsupported_bundle_format')
        files = manifest['files']
        if set(names) != set(files) | {'manifest.json'}:
            raise ValueError('manifest_mismatch')
        required = {'platforms/linux/service/phoenix_linux/server.py',
                    'platforms/linux/service/phoenix_linux/__init__.py',
                    'platforms/linux/deploy/phoenix.service'} | {'shared/web/' + name for name in ASSETS}
        if not required <= set(files):
            raise ValueError('incomplete_bundle')
        for name, digest in files.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError('bundle_checksum_mismatch')
        return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('build', 'verify'))
    parser.add_argument('bundle')
    args = parser.parse_args()
    manifest = build(args.bundle) if args.action == 'build' else verify(args.bundle)
    print(json.dumps({'files': len(manifest['files']), 'verified': True, 'signed': False}))


if __name__ == '__main__':
    main()
