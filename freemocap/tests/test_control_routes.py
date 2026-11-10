from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.api.http.app import shutdown as shutdown_module
from freemocap.api.http.capture.capture_router import capture_router
from freemocap.api.http.mocap import mocap_router as mocap
from freemocap.api.http.calibration import calibration_router as calibration
from freemocap.api.http.realtime.realtime_router import realtime_router
from freemocap.api.http.recordings.processing_router import processing_router
from freemocap.core.recording.recording_access import RecordingAccess
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@pytest.fixture
def control(tmp_path, monkeypatch):
    folder = tmp_path / 'clip'
    folder.mkdir()
    info = RecordingInfo(recording_directory=str(tmp_path), recording_name='clip')
    live = Mock(alive=True)
    service = SimpleNamespace(
        start_recording_all=AsyncMock(), stop_recording_all=AsyncMock(return_value=info),
        create_posthoc_mocap_pipeline=AsyncMock(return_value=SimpleNamespace(id='mocap-task')),
        create_posthoc_calibration_pipeline=AsyncMock(return_value=SimpleNamespace(id='calibration-task')),
        realtime_pipeline_manager=SimpleNamespace(pipelines={'live': live}, stop_pipeline=Mock(return_value=True),
                                                  stop_pipelines=Mock()),
    )
    monkeypatch.setattr(mocap, 'get_freemocap_app', lambda: service)
    monkeypatch.setattr(calibration, 'get_freemocap_app', lambda: service)
    app = FastAPI()
    app.state.recording_access = RecordingAccess()
    app.state.global_kill_flag = SimpleNamespace(value=False)
    for router in [capture_router, processing_router, realtime_router, shutdown_module.shutdown_router]:
        app.include_router(router)
    with TestClient(app) as client:
        yield client, service, folder, app


@pytest.mark.parametrize('kind', ['mocap', 'calibration'])
def test_recording_processing_binds_path_and_task(control, kind):
    client, service, folder, _ = control
    response = client.post('/recordings/clip/processing', params={'recording_parent_directory': str(folder.parent)},
                           json={'kind': kind})
    assert response.status_code == 202, response.text
    assert response.json()['task_id'] == f'{kind}-task'
    assert response.json()['recording_parent_directory'] == str(folder.parent)
    operation = getattr(service, f'create_posthoc_{kind}_pipeline')
    info = operation.call_args.kwargs['recording_info']
    assert info.recording_name == 'clip'
    assert info.recording_directory == str(folder.parent)
    # Conflicting legacy body paths and unknown discriminators never reach the manager.
    for body in [{'kind': kind, 'recording_path': '/elsewhere'}, {'kind': 'other'}]:
        assert client.post('/recordings/clip/processing', params={'recording_parent_directory': str(folder.parent)},
                           json=body).status_code == 422
    assert operation.await_count == 1


def test_stage_prerequisites_and_busy_recording(control):
    client, service, folder, app = control
    params = {'recording_parent_directory': str(folder.parent)}
    assert client.get('/recordings/clip/stages', params=params).json() == {'runs': [], 'selected_run_id': 0}
    assert client.get('/recordings/clip/runs/99/stages', params=params).status_code == 404
    response = client.post('/recordings/clip/processing', params=params,
                           json={'kind': 'mocap', 'config': {'startStage': 'filtering'}})
    assert response.status_code == 400, response.text
    service.create_posthoc_mocap_pipeline.assert_not_awaited()
    access = app.state.recording_access
    access.reserve(recording=RecordingStructure(base_directory=folder.parent, recording_name='clip'), task_id='owner')
    try:
        assert client.get('/recordings/clip/stages', params=params).status_code == 409
        assert client.post('/recordings/clip/processing', params=params, json={'kind': 'mocap'}).status_code == 409
    finally:
        access.release(task_id='owner')


@pytest.mark.parametrize('kind', ['mocap', 'calibration'])
def test_capture_stop_returns_recording_and_task(control, kind):
    client, service, folder, _ = control
    response = client.post(f'/capture/{kind}/stop', json={f'{kind}TaskConfig': {}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['task_id'] == f'{kind}-task'
    assert body['recording_path'] == str(folder)
    assert body['recording_id'] == 'clip'
    assert 'pipeline_id' not in body
    service.stop_recording_all.assert_awaited_once()
    if kind == 'calibration':
        live = service.realtime_pipeline_manager.pipelines['live']
        assert live.pubsub.publish.call_args.args[1].is_active is False
        live.exit_calibration_charuco_only_mode.assert_called_once()


def test_shutdown_requires_post(control, monkeypatch):
    client, _, _, app = control
    close = AsyncMock()
    monkeypatch.setattr(shutdown_module, 'close_camera_groups', close)
    assert client.get('/shutdown').status_code == 405
    assert app.state.global_kill_flag.value is False
    close.assert_not_awaited()
    assert client.post('/shutdown').status_code == 200
    assert app.state.global_kill_flag.value is True
    close.assert_awaited_once()


def test_realtime_stop_preserves_scope(control):
    client, service, _, _ = control
    assert client.delete('/realtime/pipelines/live').status_code == 200
    service.realtime_pipeline_manager.stop_pipeline.assert_called_once_with(pipeline_id='live')
    service.realtime_pipeline_manager.stop_pipelines.assert_not_called()


def test_command_openapi_uses_typed_recording_request(control):
    client, _, _, _ = control
    schema = client.get('/openapi.json').json()
    operation = schema['paths']['/recordings/{recording_id}/processing']['post']
    assert operation['tags'] == ['Recording processing']
    assert operation['requestBody']['content']['application/json']['schema']['discriminator']['propertyName'] == 'kind'
    assert 'get' not in schema['paths']['/shutdown']


@pytest.mark.parametrize('kind', ['mocap', 'calibration'])
@pytest.mark.parametrize('action', ['start', 'stop'])
def test_capture_state_conflicts_return_409(control, kind, action):
    from skellycam.core.camera_group.camera_errors import CameraStateConflict
    client, service, folder, _ = control
    operation = getattr(service, f'{action}_recording_all')
    operation.side_effect = CameraStateConflict('Recording state conflicts with this operation')
    body = {f'{kind}TaskConfig': {}}
    if action == 'start':
        body[f'{kind}RecordingDirectory'] = str(folder)
    response = client.post(f'/capture/{kind}/{action}', json=body)
    assert response.status_code == 409, response.text
    assert response.json()['detail'] == 'Recording state conflicts with this operation'
    getattr(service, f'create_posthoc_{kind}_pipeline').assert_not_awaited()
