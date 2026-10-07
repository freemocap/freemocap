"""Explicit installation of a prebuilt, self-contained add-on ZIP."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tomllib
import zipfile

from freemocap.core.blender.runtime import inspect_blender, run_blender


def validate_archive(path, runtime):
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != '.zip':
        raise ValueError('Select a built FreeMoCap add-on ZIP containing bundled dependencies')
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Archive contains duplicate paths')
        for name in [i.orig_filename for i in archive.infolist()]:
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
                raise ValueError('Unsafe archive path')
        manifests = [n for n in names if n.endswith('blender_manifest.toml')]
        if manifests:
            if len(manifests) != 1 or tuple(runtime['blender']) < (4, 2, 0):
                raise ValueError('Extension ZIP requires Blender 4.2 or newer')
            manifest = tomllib.loads(archive.read(manifests[0]).decode())
            if manifest['id'] != 'freemocap_blender_addon':
                raise ValueError('Not a FreeMoCap package')
            version = tuple(runtime['blender'])
            for key, valid in [('blender_version_min', lambda v: version >= v), ('blender_version_max', lambda v: version < v)]:
                if key in manifest and not valid(tuple(map(int, manifest[key].split('.')))):
                    raise ValueError('Package Blender version range does not match selected Blender')
            machine = runtime['machine'].lower()
            arch = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(machine)
            system = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'macos'}.get(runtime['system'])
            if system + '-' + str(arch) not in manifest.get('platforms', []):
                raise ValueError('Package operating system/architecture does not match selected Blender')
            prefix = manifests[0].removesuffix('blender_manifest.toml')
            entries = json.loads(archive.read(prefix + 'dependency-lock.json'))
            expected_tag = 'cp' + runtime['python'].replace('.', '')
            for entry in entries:
                filename = entry['filename']
                if filename.startswith('pyarrow-') and ('-' + expected_tag + '-') not in filename:
                    raise ValueError('Bundled PyArrow does not match Blender Python')
                content = archive.read(prefix + 'wheels/' + filename)
                if hashlib.sha256(content).hexdigest() != entry['sha256']:
                    raise ValueError('Bundled wheel checksum mismatch')
            if not any(e['filename'].startswith('pyarrow-') for e in entries):
                raise ValueError('Package does not bundle PyArrow')
            return path, 'extension'
        prefix = 'freemocap_blender_addon/'
        try:
            target = json.loads(archive.read(prefix + '_legacy_dependencies.json'))['runtime']
        except KeyError as error:
            raise ValueError('Raw source ZIP is unsupported; select a package with bundled dependencies') from error
        machine = {'amd64': 'x86_64', 'aarch64': 'arm64'}.get(runtime['machine'].lower(), runtime['machine'].lower())
        if target != [runtime['system'], machine, runtime['python']]:
            raise ValueError('Legacy package Python/OS/architecture does not match Blender')
        if prefix + '_dependencies/pyarrow/__init__.py' not in names:
            raise ValueError('Legacy package does not bundle PyArrow')
        return path, 'legacy'


def install_freemocap_blender_addon(blender_exe_path, archive_path):
    runtime = inspect_blender(blender_exe_path)
    archive, kind = validate_archive(archive_path, runtime)
    result = run_blender(blender_exe_path, dict(action='install', archive=str(archive), kind=kind))
    # Confirm a fresh process loads saved preferences and the exact installed name.
    after = inspect_blender(blender_exe_path)
    if result['package'] not in after['packages']:
        raise RuntimeError('Installed package did not remain enabled after restarting Blender')
    return dict(**result, runtime=after)
