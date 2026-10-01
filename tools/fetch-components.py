#!/usr/bin/env python3
"""Fetch pinned artifacts with streaming verification; never executes downloads."""
import argparse, hashlib, json, os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]

def fetch(destination):
    lock = json.loads((ROOT / 'components.lock.json').read_text(encoding='utf-8'))
    assert lock['schema'] == 1
    base = lock['baseUrl']
    assert base == 'https://relinkus.cn/server/components/20261002/'
    destination.mkdir(parents=True, exist_ok=True)
    for name, expected in lock['files'].items():
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('Unsafe component name')
        target = destination / name
        if target.is_symlink():
            raise ValueError('Refusing a symlink')
        if target.is_file() and target.stat().st_size == expected['bytes'] and hashlib.sha256(target.read_bytes()).hexdigest() == expected['sha256']:
            print(name + ': verified existing file')
            continue
        temporary = target.with_name(name + '.part')
        digest, length, created = hashlib.sha256(), 0, False
        try:
            with urlopen(base + name, timeout=60) as response:
                final = urlparse(response.geturl())
                if final.scheme != 'https' or final.hostname != 'relinkus.cn':
                    raise ValueError('Unexpected download destination')
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                created = True
                with os.fdopen(fd, 'wb') as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        length += len(chunk)
                        if length > expected['bytes']:
                            raise ValueError('Oversized component')
                        digest.update(chunk)
                        output.write(chunk)
            if length != expected['bytes'] or digest.hexdigest() != expected['sha256']:
                raise ValueError('Component checksum mismatch: ' + name)
            temporary.replace(target)
            print(name + ': downloaded and verified')
        except BaseException:
            # Only remove the exact temporary file created for this download.
            if created and temporary.is_file() and not temporary.is_symlink():
                temporary.unlink()
            raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=ROOT / 'components')
    fetch(parser.parse_args().directory.resolve())
