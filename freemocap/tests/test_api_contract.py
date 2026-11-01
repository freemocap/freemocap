from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.app.app import _customize_openapi, _register_routes
from freemocap.core.recording.recording_access import RecordingAccess
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def test_public_api_categories_and_camera_methods(monkeypatch):
    import freemocap.app.app as app_module
    monkeypatch.setattr(app_module.logger, "api", lambda *args: None, raising=False)
    app = FastAPI()
    _register_routes(app)
    _customize_openapi(app)
    assert str(app.url_path_for("websocket_server_connect")) == "/websocket/connect"
    schema = app.openapi()
    tags = {tag['name'] for tag in schema['tags']}
    ids = []
    for path, operations in schema['paths'].items():
        assert 'scientific' not in path.lower()
        for operation in operations.values():
            assert len(operation['tags']) == 1, (path, operation['tags'])
            assert set(operation['tags']) <= tags, (path, operation['tags'])
            ids.append(operation['operationId'])
    assert len(ids) == len(set(ids))
    assert not any('scientific' in name.lower() for name in schema['components']['schemas'])
    assert set(schema['paths']['/skellycam/camera/group/all/record/stop']) == {'post'}
    assert set(schema['paths']['/skellycam/camera/group/all/pause']) == {'put'}
    assert '/skellycam/camera/group/all/pause_unpause' not in schema['paths']
    assert set(schema['paths']['/shutdown']) == {'post'}
    for path in ('/freemocap/onnx/execution_providers', '/freemocap/onnx/session_providers'):
        assert set(schema['paths'][path]) == {'get'}
        assert schema['paths'][path]['get']['tags'] == ['ONNX']


def test_processing_blocks_calibration_edits_and_blender_launch(tmp_path, monkeypatch):
    from freemocap.api.http.calibration import calibration_router as calibration
    from freemocap.api.http.blender import blender_router as blender
    from freemocap.core.tasks.calibration.shared.calibration_update import CalibrationUpdateRequest
    app = FastAPI()
    app.state.recording_access = RecordingAccess()
    app.include_router(calibration.calibration_router)
    app.include_router(blender.blender_router)
    recording = RecordingStructure(base_directory=tmp_path, recording_name='clip')
    app.state.recording_access.reserve(recording=recording, task_id='processing')
    def unexpected(*args, **kwargs):
        raise AssertionError('Busy recording must not be read or changed')
    monkeypatch.setattr(calibration, '_save_calibration_transform', unexpected)
    monkeypatch.setattr(blender, '_open_in_blender', unexpected)
    from freemocap.core.tasks.calibration.shared.calibration_transform import CalibrationTransform, CalibrationTransformType
    request = CalibrationUpdateRequest(path=recording.full_path / 'calibration.toml',
                                       expected_mtime_ms=1, transformations=(CalibrationTransform(
                                           operation=CalibrationTransformType.MANUAL,
                                           quaternion_wxyz=(1., 0., 0., 0.), translation_mm=(0., 0., 0.)),))
    with TestClient(app) as client:
        for url, body in [('/calibration/transform', request.model_dump(mode='json')),
                          ('/blender/open', {'recordingFolderPath': str(recording.full_path)})]:
            response = client.post(url, json=body)
            assert response.status_code == 409, response.text
            assert response.json()['detail']['owner']['task_id'] == 'processing'
    assert not app.state.recording_access.readers
