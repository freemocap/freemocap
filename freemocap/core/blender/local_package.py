"""Run the dependency's standard-library host builder; Blender only installs ZIPs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import urllib.error

from filelock import FileLock

from .expected_build import addon_source, expected_build
from .helpers.addon_identity import source_hash
from .helpers.install_blender_addon import validate_archive
from .package_catalog import digest, storage_root

# Tested Blender/Python intervals; do not guess across ABI changes.
TARGETS = {
    '3.0': ('legacy', '3.9'), '3.6': ('legacy', '3.10'),
    '4.2': ('extension', '3.11'), '4.5': ('extension', '3.11'),
    '5.2': ('extension', '3.13'),
}


def build_from_dependency(runtime, requested_hash):
    root = addon_source()
    identity = expected_build()
    if requested_hash != identity['source_sha256']:
        raise RuntimeError('The selected development build differs from the installed dependency. Update the dependency or select a developer package catalog.')
    if source_hash(root) != requested_hash:
        raise RuntimeError('Bundled add-on source differs from its expected identity')
    version = '.'.join(map(str, runtime['blender'][:2]))
    kind, python = TARGETS.get(version, (None, None))
    machine = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(runtime['machine'].lower())
    platform = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'macos'}.get(runtime['system'])
    if not kind or python != runtime['python'] or platform != 'windows' or machine != 'x64':
        raise RuntimeError(f'Automatic Blender packaging is not yet supported for Blender {version}, Python {runtime["python"]}, {platform}-{machine}')
    platform += '-' + machine
    tools = root / '_host_tools'
    if not (tools/'build_addon.py').is_file():
        raise RuntimeError('Update the FreeMoCap Blender add-on dependency: this version does not include its host package builder')
    builder_hash = hashlib.sha256()
    for path in sorted(tools.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            builder_hash.update(path.relative_to(tools).as_posix().encode())
            builder_hash.update(path.read_bytes())
    key = hashlib.sha256(json.dumps([identity, version, python, platform, builder_hash.hexdigest()], sort_keys=True).encode()).hexdigest()
    cache = storage_root()
    packages = cache/'built'/key
    packages.mkdir(parents=True, exist_ok=True)
    archive, receipt = packages/'package.zip', packages/'receipt.json'
    with FileLock(packages/'build.lock', timeout=180):
        if archive.is_file() and receipt.is_file():
            checksum = digest(archive)
            try:
                intact = json.loads(receipt.read_text()).get('sha256') == checksum
            except (ValueError, OSError):
                intact = False
            if intact:
                validate_archive(archive, runtime)
                return archive, kind, checksum
        spec = importlib.util.spec_from_file_location('freemocap_host_package_builder', tools/'build_addon.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        wheels = cache/'wheels'
        wheels.mkdir(exist_ok=True)
        # One wheel writer at a time, even if different Blender versions are requested.
        with FileLock(wheels/'download.lock', timeout=180):
            try:
                builder.wheel_set(wheels, python, platform, download=False)
            except (FileNotFoundError, ValueError):
                try:
                    builder.wheel_set(wheels, python, platform, download=True)
                except (urllib.error.URLError, TimeoutError) as error:
                    raise RuntimeError('First-time Blender setup needs internet to obtain prebuilt dependencies. Reconnect and retry; cached dependencies work offline.') from error
            with tempfile.TemporaryDirectory(dir=packages) as temporary:
                options = dict(kind=kind, python=python, platform=platform, cache=wheels,
                               output=Path(temporary), provenance=identity)
                if kind == 'extension':
                    major, minor = runtime['blender'][:2]
                    options.update(blender_min=f'{major}.{minor}.0', blender_max=f'{major}.{minor+1}.0')
                built = builder.build(**options)
                validate_archive(built, runtime)
                checksum = digest(built)
                built.replace(archive)
        receipt.write_text(json.dumps(dict(sha256=checksum)), encoding='utf-8')
        return archive, kind, checksum
