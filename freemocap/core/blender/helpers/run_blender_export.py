"""Executed only by Blender; use its installed package and dependencies."""
import importlib
import json
import platform
from pathlib import Path
import sys


def enabled_packages():
    import bpy
    packages = []
    for name in bpy.context.preferences.addons.keys():
        if name.split('.')[-1] != 'freemocap_blender_addon':
            continue
        module = importlib.import_module(name)
        if getattr(module, '__freemocap_export_api__', False):
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


def execute(request):
    import bpy
    if request['action'] == 'inspect':
        return dict(blender=list(bpy.app.version), python='{}.{}'.format(*sys.version_info[:2]),
                    system=platform.system(), machine=platform.machine(), packages=enabled_packages())
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
    if request['action'] != 'export':
        raise ValueError('Unknown Blender action')
    package = select_package(request.get('package'))
    api = importlib.import_module(package + '.export_api')
    output = api.export_recording(recording_path=request['recording'], blend_file_path=request['output'],
                                  route=request['route'], config=request.get('config'), trajectory_channel=request['trajectory_channel'],
                                  run_id=request.get('run_id'), sensor_group=request.get('sensor_group'))
    return dict(output=output, package=package)


if __name__ == '__main__':
    request_path, result_path = sys.argv[sys.argv.index('--') + 1:]
    result = execute(json.loads(Path(request_path).read_text(encoding='utf-8')))
    Path(result_path).write_text(json.dumps(result), encoding='utf-8')
