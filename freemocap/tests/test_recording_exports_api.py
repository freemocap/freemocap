"""Export choices, jobs and durable inventory share one recording identity."""
from concurrent.futures import CancelledError
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.recordings.exports_router import recording_exports_router
from freemocap.api.http.posthoc import export_jobs, tasks_router
from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistry
from freemocap.core.recording.exports.recording_export_request import ChannelExportRequest
from freemocap.core.recording.recording_access import RecordingAccess
from freemocap.core.tasks.background_task_state import BackgroundTaskState
from freemocap.tests.test_wide_csv_export import recording_processing  # noqa: F401
from freemocap.tests.test_saved_reconstruction import saved_request  # noqa: F401


@pytest.fixture
def api(monkeypatch):
    app = FastAPI()
    app.state.recording_access = RecordingAccess()
    app.include_router(recording_exports_router)
    app.include_router(tasks_router.tasks_router)
    monkeypatch.setattr(export_jobs, '_jobs', {})
    monkeypatch.setattr(export_jobs, 'task_state', BackgroundTaskState())
    manager = SimpleNamespace(posthoc_pipeline_manager=SimpleNamespace(task_snapshot=TaskRegistry().snapshot),
                              sync_job_manager=SimpleNamespace(task_state=BackgroundTaskState()))
    monkeypatch.setattr(tasks_router, 'get_freemocap_app', lambda: manager)
    return app


@pytest.mark.parametrize('format', ['wide_csv', 'npy', 'npz', 'notebook'])
def test_all_file_formats_publish_and_remain_discoverable(api, recording_processing, format):  # noqa: F811
    structure, _ = recording_processing
    original = structure.data_parquet_path.read_bytes()
    params = {'recording_parent_directory': str(structure.base_directory)}
    base = f'/recordings/{structure.recording_name}'
    with TestClient(api) as client:
        choices = client.get(base + '/export-options', params=params).json()
        assert choices['selected_run_id'] == 3
        options = {'kind': 'tall_csv' if format == 'tall_csv' else 'channels', 'run_id': 3,
                   'expected_revision': choices['revision']}
        if format != 'tall_csv':
            options.update(formats=[format], data=['RAW_KEYPOINTS_3D'])
        response = client.post(base + '/exports', params=params, json=options)
        assert response.status_code == 202, response.text
        task = client.get('/tasks/' + response.json()['task_id']).json()
        assert task['status'] == 'complete', task.get('error', task)
        assert task['source_run_id'] == 3 and task['source_revision'] == choices['revision']
        inventory = client.get(base + '/exports', params={**params, 'verify': True}).json()
        assert not inventory['issues'], inventory
        assert any(item['format'] == format for item in inventory['artifacts'])
        published = {item['path'] for item in inventory['artifacts']}
        assert set(task['result']['files']) <= published
        assert all(item['integrity'] == 'valid' for item in inventory['artifacts'] if item['manifest_path'])
        assert not any(item['stale'] for item in inventory['artifacts'])
        # Task history is session-local; artifact discovery is not.
        export_jobs._jobs.clear()
        export_jobs.task_state.tasks.clear()
        assert client.get(base + '/exports', params={**params, 'verify': True}).json() == inventory
        assert client.get('/tasks/' + task['task_id']).status_code == 404
    assert structure.data_parquet_path.read_bytes() == original


def test_tall_csv_uses_complete_saved_grid(api, saved_request):  # noqa: F811
    structure = saved_request.structure
    before = structure.data_parquet_path.read_bytes()
    with TestClient(api) as client:
        params = {'recording_parent_directory': str(structure.base_directory)}
        base = f'/recordings/{structure.recording_name}'
        response = client.post(base + '/exports', params=params, json={'kind': 'tall_csv'})
        assert response.status_code == 202, response.text
        task = client.get('/tasks/' + response.json()['task_id']).json()
        assert task['status'] == 'complete', task.get('error')
        inventory = client.get(base + '/exports', params={**params, 'verify': True}).json()
        assert any(item['format'] == 'tall_csv' and item['integrity'] == 'valid' for item in inventory['artifacts'])
        assert len(task['result']['files']) == 2
    assert structure.data_parquet_path.read_bytes() == before


def test_options_and_inventory_for_unprocessed_recording(api, tmp_path):
    folder = tmp_path / 'external'
    folder.mkdir()
    (folder / 'external.blend').write_bytes(b'existing scene')
    with TestClient(api) as client:
        params = {'recording_parent_directory': str(tmp_path)}
        options = client.get('/recordings/external/export-options', params=params).json()
        assert options['revision'] is None and options['runs'] == []
        files = client.get('/recordings/external/exports', params=params).json()['artifacts']
        assert files[0]['format'] == 'blend' and files[0]['integrity'] == 'unverified'
        assert files[0]['source_revision'] is None


def test_inventory_reports_edited_and_missing_artifacts_without_hiding_other_files(api, recording_processing):  # noqa: F811
    structure, _ = recording_processing
    with TestClient(api) as client:
        params = {'recording_parent_directory': str(structure.base_directory)}
        base = '/recordings/recording'
        accepted = client.post(base + '/exports', params=params, json={
            'kind': 'channels', 'formats': ['wide_csv'], 'data': ['RAW_KEYPOINTS_3D'],
        }).json()
        result = client.get('/tasks/' + accepted['task_id']).json()['result']
        target = Path(result['files'][0])
        target.write_bytes(target.read_bytes() + b'edited')
        def artifact(verify):
            response = client.get(base + '/exports', params={**params, 'verify': verify}).json()
            return next(item for item in response['artifacts'] if item['path'] == str(target))
        assert artifact(False)['integrity'] == 'unverified'
        assert artifact(True)['integrity'] == 'changed'
        target.unlink()  # This file was generated only by this test.
        assert artifact(True)['integrity'] == 'missing'


def test_busy_stale_and_conflicting_identity_rejected_before_acceptance(api, recording_processing):  # noqa: F811
    structure, _ = recording_processing
    params = {'recording_parent_directory': str(structure.base_directory)}
    base = '/recordings/recording'
    body = {'kind': 'channels', 'formats': ['wide_csv'], 'data': ['RAW_KEYPOINTS_3D']}
    with TestClient(api) as client:
        assert client.post(base + '/exports', params=params, json={**body, 'expected_revision': 'old'}).status_code == 409
        assert client.post(base + '/exports', params=params, json={**body, 'recording_path': '/different'}).status_code == 422
        api.state.recording_access.reserve(recording=structure, task_id='processing')
        assert client.post(base + '/exports', params=params, json=body).status_code == 409
        assert client.get(base + '/export-options', params=params).status_code == 409
        assert client.get(base + '/exports', params=params).status_code == 409
    assert not export_jobs._jobs


def test_processing_reservation_cancels_export_and_waits_for_reader(api, recording_processing, monkeypatch):  # noqa: F811
    structure, _ = recording_processing
    entered, finish = Event(), Event()
    def exporting(**kwargs):
        entered.set()
        assert finish.wait(5)
        assert kwargs['cancelled']()
        raise CancelledError()
    monkeypatch.setattr(export_jobs, 'export_recording', exporting)
    options = ChannelExportRequest(formats=('wide_csv',))
    key = export_jobs.create_job(structure=structure, request=options)
    access = api.state.recording_access
    worker = Thread(target=export_jobs.run_job, args=(key, structure, options), kwargs={'access': access})
    worker.start()
    try:
        assert entered.wait(5)
        access.reserve(recording=structure, task_id='processing')
        assert not access.ready(task_id='processing')
    finally:
        finish.set()
        worker.join(5)
    assert not worker.is_alive()
    assert export_jobs.job_state(key)['status'] == 'cancelled'
    assert access.ready(task_id='processing')


def test_blender_job_preserves_all_options_and_reports_artifact(api, recording_processing, monkeypatch):  # noqa: F811
    structure, _ = recording_processing
    calls = []
    def exporting(**kwargs):
        calls.append(kwargs)
        output = Path(kwargs['recording_folder_path']) / 'recording.blend'
        output.write_bytes(b'validated by Blender executor')
        return str(output)
    monkeypatch.setattr(export_jobs, 'export_to_blender', exporting)
    with TestClient(api) as client:
        params = {'recording_parent_directory': str(structure.base_directory)}
        response = client.post('/recordings/recording/exports', params=params, json={
            'kind': 'blender', 'route': 'parquet_constraints', 'runId': 3, 'sensorGroup': 'a',
            'trajectoryChannel': 'MAPPED_KEYPOINTS_3D', 'autoOpenBlendFile': False,
            'blenderExportConfig': {'formats': ['fbx', 'bvh'], 'restPose': 'apose'},
        })
        assert response.status_code == 202, response.text
        task = client.get('/tasks/' + response.json()['task_id']).json()
        assert task['status'] == 'complete', task.get('error', task)
        assert task['result']['blender_file_path'].endswith('recording.blend')
    assert calls[0]['run_id'] == 3 and calls[0]['sensor_group'] == 'a'
    assert calls[0]['blender_export_config']['formats'] == ['fbx', 'bvh']
    assert calls[0]['blender_export_config']['rest_pose'] == 'apose'
    assert not calls[0]['open_file_on_completion']
    assert callable(calls[0]['cancelled'])
