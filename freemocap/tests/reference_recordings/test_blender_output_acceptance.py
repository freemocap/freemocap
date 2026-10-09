"""Reopen production Blender outputs and reject a saved scene with wrong motion."""
import os
from pathlib import Path
import subprocess

import pytest

from freemocap.core.blender import runtime
from freemocap.core.recording.exports.publication import digest
from freemocap.tools.datasets.blender_validation import preflight_blender, validate_blender
from freemocap.tools.datasets.workflow import checked_ready


def reference(name):
    configured = os.environ.get('FREEMOCAP_PROVENANCE_PREPARED_ROOT')
    if not configured:
        pytest.skip('Set FREEMOCAP_PROVENANCE_PREPARED_ROOT to complete standard reference outputs')
    ready = checked_ready(Path(configured) / name)
    assert ready is not None
    return Path(ready['recording']), ready['result']['validation']


@pytest.mark.e2e
@pytest.mark.parametrize('name', ['freemocap_test_data', 'freemocap_sample_data'])
def test_saved_blender_matches_all_reference_frames(name):
    recording, validation = reference(name)
    paths = [recording / f'{name}.blend', recording / f'{name}_data.parquet']
    before = [digest(path) for path in paths]
    checks = validate_blender(recording, validation,
        blender_path=validation['outputs']['artifacts']['blender']['checks']['executable'])
    assert checks['frames'] == validation['frames']
    assert checks['finite_segment_poses'] > 0
    assert [digest(path) for path in paths] == before


@pytest.mark.e2e
@pytest.mark.parametrize('target', ['landmark', 'armature'])
def test_saved_blender_rejects_changed_geometry(tmp_path, target):
    recording, validation = reference('freemocap_test_data')
    original = recording / f'{recording.name}.blend'
    before = digest(original)
    blender, prepared = preflight_blender(validation['outputs']['artifacts']['blender']['checks']['executable'])
    output = tmp_path / 'wrong-geometry.blend'
    script = tmp_path / 'alter_scene.py'
    script.write_text('''import bpy, sys
source, output, target = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.open_mainfile(filepath=source, load_ui=False, use_scripts=False)
obj = (bpy.data.objects['pelvis_origin'] if target == 'landmark'
       else next(obj for obj in bpy.data.objects if obj.type == 'ARMATURE'))
obj.animation_data_clear()
obj.location.x += 1.0
bpy.ops.wm.save_as_mainfile(filepath=output)
''')
    result = runtime.run_external([str(blender), '--background', '--python-exit-code', '1', '--python', str(script),
        '--', str(original), str(output), target], cwd=tmp_path, env=runtime.environment(prepared.profile),
        timeout=120, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert result.returncode == 0, result.stdout
    with pytest.raises(RuntimeError, match='Not equal to tolerance'):
        runtime.run_blender(blender, dict(action='validate_scene', package=prepared.package,
            recording=str(recording), output=str(output), run_id=validation['run_id'],
            sensor_group=validation['sensor_group'], source_sha256=validation['parquet_sha256']), profile=prepared.profile)
    assert digest(original) == before
