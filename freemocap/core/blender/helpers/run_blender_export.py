"""Executed only by Blender; use its installed package and dependencies."""
import importlib
import json
import platform
from pathlib import Path
import sys
import importlib.util

_spec = importlib.util.spec_from_file_location('fmc_identity', Path(__file__).with_name('addon_identity.py'))
identity_tools = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(identity_tools)


def enabled_packages():
    import bpy
    packages = []
    for name in bpy.context.preferences.addons.keys():
        if name.split('.')[-1] != 'freemocap_blender_addon':
            continue
        packages.append(name)
    return packages


def select_package(requested=None):
    packages = enabled_packages()
    if requested is not None:
        if requested not in packages:
            raise ValueError('Requested FreeMoCap package is not enabled: ' + requested)
        return requested
    if len(packages) != 1:
        raise ValueError('Install and enable one bundled FreeMoCap add-on in this Blender version, '
                         'or select its exact package name. Enabled packages: ' + repr(packages))
    return packages[0]


def inspect_package(name, expected, development_hash=None):
    detail = dict(package=name, version=None, identity=None, dependencies=None,
                  build_match='unverified', ready=False, errors=[])
    try:
        module = importlib.import_module(name)
        detail['version'] = getattr(module, '__version__', None)
        detail['path'] = str(Path(module.__file__).parent)
        if not getattr(module, '__freemocap_export_api__', False):
            detail['errors'].append('Add-on does not provide the FreeMoCap export API')
        try:
            identity = identity_tools.read_identity(Path(module.__file__).parent)
            detail['identity'] = identity
            version = '.'.join(str(int(p)) for p in str(detail['version']).lstrip('v').split('.'))
            if version != identity.get('version'):
                detail['errors'].append('Add-on version disagrees with its build identity')
            if identity.get('export_api_version') != expected.get('export_api_version', 1):
                detail['errors'].append('Unsupported add-on export API version')
            target = development_hash or expected.get('source_sha256')
            detail['build_match'] = ('development' if development_hash else 'expected') if identity['source_sha256'] == target else 'different'
            if detail['build_match'] == 'different':
                detail['errors'].append('Installed add-on differs from the expected build. Install the matching package or explicitly select this build for development.')
        except Exception as error:
            detail['errors'].append('Unverified add-on build: ' + str(error))
        try:
            dependencies = importlib.import_module(name + '.utilities.dependencies')
            detail['dependencies'] = dependencies.dependency_report()
            arrow = dependencies.require_module('pyarrow')
            parquet = dependencies.parquet_module()
            sink = arrow.BufferOutputStream()
            sample = arrow.table({'value': [1.0, None]})
            parquet.write_table(sample, sink, compression='zstd')
            if not parquet.read_table(arrow.BufferReader(sink.getvalue())).equals(sample):
                raise RuntimeError('Parquet round-trip check failed')
            identity = detail['identity']
            if identity:
                if identity['python'] != '{}.{}'.format(*sys.version_info[:2]):
                    raise RuntimeError('Package targets a different Blender Python version')
                machine = {'amd64': 'x64', 'x86_64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(platform.machine().lower())
                if identity['platform'] != platform.system().lower() + '-' + str(machine):
                    # Package naming uses macos, while Python uses Darwin.
                    if not (platform.system() == 'Darwin' and identity['platform'] == 'macos-' + str(machine)):
                        raise RuntimeError('Package targets a different operating system/architecture')
                entries = json.loads((Path(module.__file__).parent / 'dependency-lock.json').read_text())
                pin = next(e['version'] for e in entries if e['name'] == 'pyarrow')
                if arrow.__version__ != pin:
                    raise RuntimeError('Loaded PyArrow version differs from the bundled dependency lock')
        except Exception as error:
            detail['errors'].append(str(error))
    except Exception as error:
        detail['errors'].append(str(error))
    detail['ready'] = not detail['errors']
    return detail


def execute(request):
    import bpy
    if request['action'] == 'inspect':
        packages = enabled_packages()
        return dict(blender=list(bpy.app.version), python='{}.{}'.format(*sys.version_info[:2]),
                    system=platform.system(), machine=platform.machine(), packages=packages,
                    expected=request.get('expected', {}),
                    package_details=[inspect_package(name, request.get('expected', {}), request.get('development_build_hash')) for name in packages])
    if request['action'] == 'install':
        archive = request['archive']
        if request['kind'] == 'extension':
            repos = bpy.context.preferences.extensions.repos
            repo = next((r for r in repos if r.module == 'freemocap_local'), None)
            if repo is None:
                repo = repos.new(name='FreeMoCap local packages', module='freemocap_local')
                repo.use_remote_url = False
            if repo.use_remote_url:
                raise ValueError('FreeMoCap local repository is configured as remote')
            result = bpy.ops.extensions.package_install_files(filepath=archive, repo=repo.module, enable_on_install=True)
            package = 'bl_ext.' + repo.module + '.freemocap_blender_addon'
        else:
            result = bpy.ops.preferences.addon_install(filepath=archive, overwrite=True)
            package = 'freemocap_blender_addon'
            bpy.ops.preferences.addon_enable(module=package)
        if result != {'FINISHED'}:
            raise RuntimeError('Blender did not finish installing the package')
        select_package(package)
        # Verify bundled binary dependencies before reporting success.
        importlib.import_module(package + '.utilities.dependencies').parquet_module()
        bpy.ops.wm.save_userpref()
        return dict(package=package)
    if request['action'] not in ('export', 'validate_scene'):
        raise ValueError('Unknown Blender action')
    package = select_package(request.get('package'))
    detail = inspect_package(package, request.get('expected', {}), request.get('development_build_hash'))
    if not detail['ready']:
        raise ValueError('Blender export is not ready: ' + '; '.join(detail['errors']))
    if request['action'] == 'validate_scene':
        spec = importlib.util.spec_from_file_location('saved_scene_validation', Path(__file__).with_name('validate_saved_scene.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.validate(request, package)
        return dict(result, package=package, addon_identity=detail['identity'])
    api = importlib.import_module(package + '.export_api')
    output = api.export_recording(recording_path=request['recording'], blend_file_path=request['output'],
                                  route=request['route'], config=request.get('config'), trajectory_channel=request['trajectory_channel'],
                                  run_id=request.get('run_id'), sensor_group=request.get('sensor_group'))
    if request.get('source_sha256'):
        bpy.context.scene['freemocap_source_sha256'] = request['source_sha256']
        # Preserve the source identity in the saved artifact, including after
        # the recording directory is moved by dataset publication.
        bpy.ops.wm.save_as_mainfile(filepath=output)
    return dict(output=output, package=package)


if __name__ == '__main__':
    request_path, result_path = sys.argv[sys.argv.index('--') + 1:]
    try:
        result = execute(json.loads(Path(request_path).read_text(encoding='utf-8')))
    except Exception as error:
        Path(result_path).write_text(json.dumps(dict(error=str(error))), encoding='utf-8')
        raise
    Path(result_path).write_text(json.dumps(result), encoding='utf-8')
