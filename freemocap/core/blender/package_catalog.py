"""Resolve prebuilt packages on the host; never install Python packages in Blender."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

from .helpers.install_blender_addon import validate_archive

def load_catalog():
    """Optional developer override; normal exports build from the dependency."""
    path = Path(os.environ['FREEMOCAP_BLENDER_PACKAGE_CATALOG']).expanduser().resolve()
    return json.loads(path.read_text(encoding='utf-8')), path


def storage_root():
    if override := os.environ.get('FREEMOCAP_BLENDER_STORAGE'):
        return Path(override).expanduser().resolve()
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.cache'))
    return base / 'freemocap' / 'blender'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def resolve_package(runtime, source_hash):
    """A catalog is pinned application configuration, not an untrusted search result."""
    if not os.environ.get('FREEMOCAP_BLENDER_PACKAGE_CATALOG'):
        from .local_package import build_from_dependency
        return build_from_dependency(runtime, source_hash)
    catalog, catalog_path = load_catalog()
    if catalog.get('schema_version') != 1:
        raise ValueError('Unsupported Blender package catalog')
    version = '.'.join(map(str, runtime['blender'][:2]))
    machine = {'amd64': 'x64', 'x86_64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(runtime['machine'].lower())
    platform = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'macos'}.get(runtime['system'])
    candidates = [p for p in catalog['packages'] if p['source_sha256'] == source_hash
                  and p['blender'] == version and p['python'] == runtime['python']
                  and p['platform'] == f'{platform}-{machine}']
    if len(candidates) != 1:
        raise RuntimeError(f'No unique developer Blender package for the required build on Blender {version}, '
                           f'Python {runtime["python"]}, {platform}-{machine}. This runtime/build combination is not supported by the available packages.')
    entry = candidates[0]
    checksum = entry['sha256']
    if len(checksum) != 64 or any(c not in '0123456789abcdef' for c in checksum):
        raise ValueError('Invalid package checksum in catalog')
    cache = storage_root() / 'packages'
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / (checksum + '.zip')
    if not archive.is_file() or digest(archive) != checksum:
        with tempfile.TemporaryDirectory(dir=cache) as temporary:
            pending = Path(temporary) / 'package.zip'
            if entry.get('path'):
                # Local catalogs support bundled artifacts and explicit developer builds.
                shutil.copyfile(catalog_path.parent / entry['path'], pending)
            elif entry.get('url', '').startswith('https://'):
                with urllib.request.urlopen(entry['url'], timeout=120) as response, pending.open('wb') as output:
                    if not response.geturl().startswith('https://'):
                        raise ValueError('Package download redirected away from HTTPS')
                    shutil.copyfileobj(response, output)
            else:
                raise RuntimeError('Required Blender package has not been distributed with this FreeMoCap build')
            if digest(pending) != checksum:
                raise ValueError('Downloaded Blender package checksum mismatch')
            pending.replace(archive)
    _, kind = validate_archive(archive, runtime)
    with zipfile.ZipFile(archive) as bundle:
        prefix = '' if kind == 'extension' else 'freemocap_blender_addon/'
        identity = json.loads(bundle.read(prefix + 'build-info.json'))
    if identity['source_sha256'] != source_hash or identity['export_api_version'] != 1:
        raise ValueError('Blender package identity does not match catalog requirement')
    return archive, kind, checksum
