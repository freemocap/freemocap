"""Opt-in real Blender integration through core HTTP endpoints.

FREEMOCAP_BLENDER_EXE and FREEMOCAP_BLENDER_ZIP select a local runtime/package.
Prepared recordings come from the core dataset publication workflow. Tests copy
inputs, use disposable Blender preferences, and never install into user profiles.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
from freemocap.core.blender.runtime import environment
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.blender.blender_router import blender_router
from freemocap.tools.datasets.workflow import checked_ready
from freemocap.tools.datasets.preparation import file_digest
from freemocap.system.recording_status.recording_status import compute_recording_status

pytestmark = pytest.mark.e2e


@pytest.fixture(scope='module')
def installed_blender():
    blender, archive = os.environ.get('FREEMOCAP_BLENDER_EXE'), os.environ.get('FREEMOCAP_BLENDER_ZIP')
    if not blender or not archive:
        pytest.skip('Set FREEMOCAP_BLENDER_EXE and FREEMOCAP_BLENDER_ZIP for real Blender tests')
    with tempfile.TemporaryDirectory(prefix='fmc-core-test-') as temporary, pytest.MonkeyPatch.context() as env:
        root = Path(temporary)
        env.setenv('BLENDER_USER_RESOURCES', str(root))
        for variable, folder in [('BLENDER_USER_CONFIG', 'config'), ('BLENDER_USER_SCRIPTS', 'scripts'),
                                  ('BLENDER_USER_DATAFILES', 'datafiles'), ('BLENDER_USER_EXTENSIONS', 'extensions')]:
            path = root / folder; path.mkdir()
            env.setenv(variable, str(path))
        app = FastAPI(); app.include_router(blender_router)
        client = TestClient(app)
        response = client.post('/blender/addon/install', json=dict(blenderExePath=blender, archivePath=archive))
        assert response.status_code == 200, response.text
        package = response.json()['package']
        yield client, blender, package


@pytest.mark.parametrize('dataset', ['freemocap_test_data', 'freemocap_sample_data'])
@pytest.mark.parametrize('route', ['parquet_segments', 'parquet_constraints'])
def test_prepared_recording_export(installed_blender, tmp_path, dataset, route):
    client, blender, package = installed_blender
    prepared = Path(os.environ.get('FREEMOCAP_PREPARED_DATA_ROOT', Path.home() / 'freemocap_data/testing/prepared')) / dataset
    ready = checked_ready(prepared)
    assert ready is not None, 'Prepare reference data with the core dataset workflow first'
    source = Path(ready['recording'])
    parquet = source / (dataset + '_data.parquet')
    before = file_digest(parquet)
    assert before == ready['result']['validation']['parquet_sha256']
    recording = tmp_path / dataset; recording.mkdir()
    shutil.copy2(parquet, recording / parquet.name)
    for folder in ('annotated_videos', 'synchronized_videos'):
        if (source / folder).is_dir():
            shutil.copytree(source / folder, recording / folder)
    assert compute_recording_status(recording).blender_export_ready
    response = client.post('/blender/export', json=dict(recordingFolderPath=str(recording), blenderExePath=blender,
        autoOpenBlendFile=False, route=route, package=package, blenderExportConfig=(dict(formats=['fbx'], rest_pose='apose', apply_foot_locking=True) if route == 'parquet_constraints' else {})))
    assert response.status_code == 200, response.text
    output = Path(response.json()['blender_file_path'])
    assert output.is_file() and output.stat().st_size > 10000
    inspection = tmp_path / 'inspect_scene.py'
    inspection.write_text("""import bpy, sys
route = sys.argv[sys.argv.index('--') + 1]
roots = [o for o in bpy.data.objects if o.get('import_route') == route]
assert len(roots) == 1
root = roots[0]
assert any(o.type == 'ARMATURE' for o in bpy.data.objects)
assert any(o.name.startswith('skelly_mesh') for o in bpy.data.objects)
assert any(o.name.startswith('video_') for o in bpy.data.objects)
assert any(o.name.startswith('Capture_') for o in bpy.data.objects)
if route == 'parquet_constraints': assert 'animation_cleanup' in root
bpy.context.scene.frame_set(bpy.context.scene.frame_end)
""", encoding='utf-8')
    reopened = subprocess.run([blender, '--background', str(output), '--python-exit-code', '1',
        '--python', str(inspection), '--', route], cwd=tmp_path, env=environment(), capture_output=True,
        text=True, encoding='utf-8', errors='replace', timeout=120)
    assert reopened.returncode == 0, reopened.stdout + reopened.stderr
    if route == 'parquet_constraints':
        assert list((recording / '3d_models').glob('*.fbx'))
    assert file_digest(parquet) == before
    assert checked_ready(prepared) == ready
