"""Opt-in real PyInstaller/Blender boundary, without building the entire UI/server."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

import pytest

from freemocap.core.blender.expected_build import write_bundled_build
from freemocap.core.blender.package_catalog import digest
from freemocap.core.blender.runtime import environment, inspect_blender
from freemocap.tools.datasets.workflow import checked_ready

pytestmark = pytest.mark.e2e


def test_frozen_backend_prepares_and_exports(tmp_path, monkeypatch):
    if os.environ.get('FREEMOCAP_RUN_FROZEN_TESTS') != '1':
        pytest.skip('Set FREEMOCAP_RUN_FROZEN_TESTS=1 to build the frozen probe')
    from freemocap.tests.blender_test_dependency import install_dependency, seed_wheels
    blender = os.environ['FREEMOCAP_BLENDER_EXE']
    source = install_dependency(tmp_path/'dependency', monkeypatch)
    root = Path(__file__).resolve().parents[2]
    identity_file = tmp_path/'bundled-build.json'
    required = write_bundled_build(identity_file)
    entry = tmp_path/'frozen_blender.py'
    entry.write_text('''import json, sys
from pathlib import Path
from freemocap.core.blender.expected_build import expected_build
from freemocap.core.blender.preparation import prepare_blender
from freemocap.core.blender.runtime import run_blender
assert getattr(sys, 'frozen', False)
request = json.loads(Path(sys.argv[1]).read_text())
assert expected_build() == request.pop('expected')
blender = request.pop('blender')
import urllib.request
urllib.request.urlopen = lambda *a, **kw: (_ for _ in ()).throw(AssertionError('offline: no GitHub or PyPI calls allowed'))
prepared = prepare_blender(blender)
assert prepared.profile is not None
request['package'] = prepared.package
result = run_blender(blender, request, profile=prepared.profile)
assert Path(result['output']).stat().st_size > 10000
print('FROZEN_BLENDER_OK')
''', encoding='utf-8')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
               '--distpath', str(tmp_path/'dist'), '--workpath', str(tmp_path/'work'),
               '--specpath', str(tmp_path), '--paths', str(root),
               '--add-data', str(identity_file) + os.pathsep + 'freemocap/core/blender']
    for name in ('run_blender_export.py', 'addon_identity.py'):
        command += ['--add-data', str(root/'freemocap/core/blender/helpers'/name) + os.pathsep + 'freemocap/core/blender/helpers']
    command += ['--add-data', str(source) + os.pathsep + 'freemocap/core/blender/addon_source/freemocap_blender_addon']
    command += [str(entry)]
    build = subprocess.run(command, capture_output=True, text=True, errors='replace', timeout=300)
    (tmp_path/'freeze.log').write_text(build.stdout + build.stderr, encoding='utf-8')
    assert build.returncode == 0, build.stdout + build.stderr
    binary = tmp_path/'dist/frozen_blender'/('frozen_blender.exe' if os.name == 'nt' else 'frozen_blender')
    # Move the bundle away from build paths, matching Electron's unpacked backend.
    relocated = tmp_path/'electron resources with spaces'
    shutil.copytree(binary.parent, relocated)
    binary = relocated/binary.name
    with tempfile.TemporaryDirectory(prefix='fmf-') as temporary:
        cache = Path(temporary)
        env = environment(cache/'normal')
        env['FREEMOCAP_BLENDER_STORAGE'] = str(cache/'managed')
        runtime = inspect_blender(blender)
        seed_wheels(cache/'managed/wheels', runtime['python'])
        env.pop('FREEMOCAP_BLENDER_PACKAGE_CATALOG', None)
        for dataset in ('freemocap_test_data', 'freemocap_sample_data'):
            ready = checked_ready(Path(os.environ['FREEMOCAP_PREPARED_DATA_ROOT'])/dataset)
            assert ready is not None
            request = dict(expected=required, blender=blender, action='export', recording=ready['recording'],
                output=str(tmp_path/(dataset+'.blend')), route='parquet_segments', trajectory_channel='LANDMARKS_3D',
                development_build_hash=None, config={'export_3d_model': {'formats': []}})
            request_path = tmp_path/'request.json'
            request_path.write_text(json.dumps(request), encoding='utf-8')
            result = subprocess.run([str(binary), str(request_path)], cwd=cache, env=env,
                capture_output=True, text=True, errors='replace', timeout=180)
            (tmp_path/(dataset+'.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
            assert result.returncode == 0 and 'FROZEN_BLENDER_OK' in result.stdout, result.stdout + result.stderr
        assert not (cache/'normal/config/userpref.blend').exists()
        assert len(list((cache/'managed/profiles').glob('*.json'))) == 1
