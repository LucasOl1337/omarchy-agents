#!/usr/bin/env python3
"""Install an immutable runtime generation and atomically select its entry point.

QML components and imported JS are cached by URL in the long-running shell.
Changing files in place can leave old code running after a plugin reload.
"""
import argparse
import hashlib
import json
from pathlib import Path
import os
import shutil
import tempfile


def deploy(source, destination):
    source, destination = Path(source).resolve(), Path(destination).expanduser().resolve()
    files = sorted([*source.glob('*.qml'), *source.glob('*.js'),
                    *(p for p in (source / 'bin').iterdir() if p.is_file()),
                    *(p for p in (source / 'assets').iterdir() if p.is_file())])
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(source)).encode() + b'\0' + path.read_bytes())
    generation = digest.hexdigest()[:20]
    runtime = destination / '.runtime' / generation
    runtime.parent.mkdir(parents=True, exist_ok=True)
    if not runtime.exists():
        temporary = Path(tempfile.mkdtemp(prefix='.staging-', dir=runtime.parent))
        try:
            for path in files:
                target = temporary / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
            temporary.rename(runtime)
        finally:
            if temporary.exists(): shutil.rmtree(temporary)
    manifest = json.loads((source / 'manifest.json').read_text())
    manifest['entryPoints']['barWidget'] = '.runtime/' + generation + '/Panel.qml'
    # Publish only after every import and collector exists at the new URL.
    with tempfile.NamedTemporaryFile('w', prefix='.manifest-', dir=destination, delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(manifest, handle, indent=2)
        handle.write('\n')
    try:
        os.chmod(temporary, 0o644)
        temporary.replace(destination / 'manifest.json')
    finally:
        temporary.unlink(missing_ok=True)
    return dict(generation=generation, version=manifest['version'], entryPoint=str(runtime / 'Panel.qml'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', default=str(Path.home() / '.config/omarchy/plugins/lol.agents'))
    args = parser.parse_args()
    print(json.dumps(deploy(Path(__file__).resolve().parents[1], args.destination)))


if __name__ == '__main__': main()
