"""Host boundary regression tests; no Blender installation required."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.core.blender import runtime
from freemocap.core.blender.export_to_blender import export_to_blender
from freemocap.core.blender.helpers.install_blender_addon import validate_archive
from freemocap.api.http.blender.blender_router import blender_router


def test_process_failure_cannot_pass_with_old_output(tmp_path):
    blender = tmp_path / 'blender.exe'; blender.touch()
    (tmp_path / 'recording_data.parquet').touch()
    output = tmp_path / 'old.blend'; output.write_bytes(b'old successful scene')
    with patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='failed binary import')):
        with pytest.raises(RuntimeError, match='failed binary import'):
            export_to_blender(tmp_path, blend_file_path=output, blender_exe_path=blender, open_file_on_completion=False)
    assert output.read_bytes() == b'old successful scene'


def test_process_isolation_and_missing_result(tmp_path, monkeypatch):
    blender = tmp_path / 'blender.exe'; blender.touch()
    monkeypatch.setenv('PYTHONPATH', 'foreign packages')
    monkeypatch.setenv('PYTHONHOME', 'foreign runtime')
    def launch(command, **kwargs):
        assert Path(kwargs['cwd']) != Path.cwd()
        assert 'PYTHONPATH' not in kwargs['env'] and 'PYTHONHOME' not in kwargs['env']
        assert command[command.index('--python-exit-code') + 1] == '1'
        return SimpleNamespace(returncode=0, stdout='partial execution')
    with patch.object(runtime.subprocess, 'run', side_effect=launch):
        with pytest.raises(RuntimeError, match='partial execution'):
            runtime.inspect_blender(blender)


def test_raw_source_and_wrong_abi_packages_rejected(tmp_path):
    archive = tmp_path / 'source.zip'
    runtime_info = dict(blender=[3, 0, 0], python='3.9', system='Windows', machine='AMD64')
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('freemocap_blender_addon/__init__.py', '')
    with pytest.raises(ValueError, match='Raw source ZIP'):
        validate_archive(archive, runtime_info)
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('freemocap_blender_addon/_legacy_dependencies.json', json.dumps(dict(runtime=['Windows', 'x86_64', '3.13'])))
    with pytest.raises(ValueError, match='does not match'):
        validate_archive(archive, runtime_info)


@pytest.mark.parametrize('name', ['../escape', 'C:/escape', 'nested\\escape'])
def test_archive_traversal_rejected(tmp_path, name):
    archive = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        info = zipfile.ZipInfo(name)
        info.filename = name  # Preserve malformed separators; ZipInfo normalizes on Windows.
        z.writestr(info, '')
    with pytest.raises(ValueError, match='Unsafe archive path'):
        validate_archive(archive, {})


def test_api_forwards_new_route_without_detector_gate(tmp_path):
    blender = tmp_path / 'blender.exe'; blender.touch()
    app = FastAPI(); app.include_router(blender_router)
    with patch('freemocap.api.http.blender.blender_router.export_to_blender') as export:
        response = TestClient(app).post('/blender/export', json=dict(recordingFolderPath=str(tmp_path),
            blenderExePath=str(blender), autoOpenBlendFile=False, route='parquet_constraints',
            runId=3, sensorGroup='cameras', package='bl_ext.local.freemocap_blender_addon'))
    assert response.status_code == 200, response.text
    assert export.call_args.kwargs['route'] == 'parquet_constraints'
    assert export.call_args.kwargs['run_id'] == 3
    assert export.call_args.kwargs['sensor_group'] == 'cameras'


def test_invalid_route_rejected_by_api(tmp_path):
    app = FastAPI(); app.include_router(blender_router)
    response = TestClient(app).post('/blender/export', json=dict(recordingFolderPath=str(tmp_path), route='made_up'))
    assert response.status_code == 422


def test_export_options_reach_blender_and_invalid_native_options_fail_early(tmp_path):
    blender = tmp_path / 'blender.exe'; blender.touch()
    (tmp_path / 'recording_data.parquet').touch()
    output = tmp_path / 'scene.blend'
    def export(executable, request, **kwargs):
        assert request['config']['add_rig']['rest_pose'] == 'apose'
        assert request['config']['motion_cleanup']['apply_foot_locking'] is True
        assert request['config']['export_3d_model']['formats'] == ['bvh']
        output.write_bytes(b'blend')
        return dict(output=str(output))
    with patch('freemocap.core.blender.export_to_blender.prepare_blender', return_value=SimpleNamespace(package='test', profile=None)), patch('freemocap.core.blender.export_to_blender.run_blender', side_effect=export) as launch:
        export_to_blender(tmp_path, blend_file_path=output, blender_exe_path=blender,
            route='parquet_constraints', open_file_on_completion=False,
            blender_export_config=dict(restPose='apose', applyFootLocking=True, formats=['bvh']))
        with pytest.raises(ValueError, match='Saved segment poses'):
            export_to_blender(tmp_path, blender_exe_path=blender,
                blender_export_config=dict(apply_foot_locking=True))
        assert launch.call_count == 1


def test_blender_option_validation():
    from freemocap.core.blender.blender_export_config import BlenderExportConfig
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        BlenderExportConfig(formats=['gltf'])
    for route in ('parquet_segments', 'parquet_constraints', 'legacy_npy'):
        assert BlenderExportConfig(formats=['fbx', 'bvh']).addon_payload(route)['export_3d_model']['formats'] == ['fbx', 'bvh']
    assert BlenderExportConfig().addon_payload('parquet_segments')['export_3d_model']['formats'] == []


@pytest.mark.parametrize('enabled,cancelled,failure', [(True,False,False),(False,False,False),(True,True,False),(True,False,True)])
def test_processing_completion_uses_exporter_without_losing_publication(enabled, cancelled, failure, tmp_path):
    from freemocap.core.pipeline.posthoc.mocap_pipeline import complete_mocap, MocapWorkerRequest
    from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
    config = PosthocMocapPipelineConfig(exportTallCsv=False, exportToBlender=enabled,
        autoOpenBlendFile=False, blenderImportRoute='parquet_constraints', blenderPackage='test.package',
        blenderExportConfig=dict(rest_pose='apose', formats=['bvh']), detectorType='rtmpose')
    reports = []
    request = Mock(spec=MocapWorkerRequest, config=config, ipc=SimpleNamespace(should_continue=not cancelled),
        recording=SimpleNamespace(full_recording_path=tmp_path), report=lambda *args: reports.append(args))
    with patch('freemocap.core.blender.export_to_blender.export_to_blender',
        side_effect=RuntimeError('package unavailable') if failure else None, return_value=str(tmp_path/'output.blend')) as export:
        complete_mocap(request)
    assert export.call_count == int(enabled and not cancelled)
    assert str(reports[-1][0]) == 'complete'
    if enabled and not cancelled:
        assert export.call_args.kwargs['route'] == 'parquet_constraints'
        assert export.call_args.kwargs['blender_export_config']['rest_pose'] == 'apose'
        assert export.call_args.kwargs['blender_export_config']['formats'] == ['bvh']
        assert ('Blender export failed' in reports[-1][1]) == failure
