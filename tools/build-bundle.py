#!/usr/bin/env python3
"""Package only declared public source, locked components and third-party licenses."""
import argparse, hashlib, json, shutil, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = '2.1.3'

def build(components, output):
    lock = json.loads((ROOT / 'components.lock.json').read_text(encoding='utf-8'))
    assert lock['bundleVersion'] == VERSION
    for name, expected in lock['files'].items():
        item = components / name
        if item.is_symlink() or not item.is_file() or item.stat().st_size != expected['bytes'] or hashlib.sha256(item.read_bytes()).hexdigest() != expected['sha256']:
            raise ValueError('Component checksum mismatch: ' + name)
    ws = ROOT / 'node_modules/ws'
    if json.loads((ws / 'package.json').read_text())['version'] != '8.21.3':
        raise ValueError('Run npm ci --ignore-scripts first')
    bundle = output / ('room-node-' + VERSION)
    archive = output / ('Relink-Room-Node-' + VERSION + '.zip')
    if bundle.exists() or archive.exists():
        raise ValueError('Output exists; choose a new output directory')
    bundle.mkdir(parents=True)
    files = ['setup.sh', 'manage.py', 'install-node.py', 'README.md', 'LICENSE',
             'THIRD_PARTY_NOTICES.md', 'relink-node-setup.example.json']
    for name in files:
        shutil.copyfile(ROOT / name, bundle / name)
    for directory in ['agent', 'docs', 'licenses']:
        shutil.copytree(ROOT / directory, bundle / directory)
    shutil.copytree(ws, bundle / 'agent/node_modules/ws', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in lock['files']:
        shutil.copyfile(components / name, bundle / name)
    hashes = {}
    for file in sorted(bundle.rglob('*')):
        if file.is_symlink():
            raise ValueError('Unexpected package symlink')
        if file.is_file():
            hashes[file.relative_to(bundle).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    (bundle / 'manifest.json').write_text(json.dumps({'version': VERSION, 'files': hashes}, indent=2) + '\n', encoding='utf-8')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for file in sorted(bundle.rglob('*')):
            if file.is_file():
                info = zipfile.ZipInfo(file.relative_to(bundle).as_posix(), (2026, 10, 2, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (0o100755 if file.name == 'setup.sh' else 0o100644) << 16
                zipped.writestr(info, file.read_bytes(), compresslevel=9)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + '.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size, 'sha256': digest, 'files': len(hashes)+1}))
    return bundle

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--components', type=Path, default=ROOT / 'components')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    build(args.components.resolve(), args.output.resolve())
