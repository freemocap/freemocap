"""Recording identity is a validated folder name scoped to a resolved parent."""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.core.recording import recording_location as locations
from freemocap.core.recording.recording_access import RecordingAccess
from freemocap.api.http.recordings.recording_access import RecordingReadRoute
from freemocap.api.http.recordings.recording_location import recording_location
from fastapi import APIRouter


def test_default_custom_and_absolute_paths_identify_the_same_recording(tmp_path, monkeypatch):
    folder = tmp_path / 'walking'
    folder.mkdir()
    monkeypatch.setattr(locations, 'get_default_freemocap_recordings_path', lambda: tmp_path)
    default = locations.resolve_recording('walking')
    assert default == locations.resolve_recording('walking', tmp_path)
    assert default == locations.recording_from_path(folder)
    other = tmp_path / 'another-root'
    (other / 'walking').mkdir(parents=True)
    assert locations.resolve_recording('walking', other) != default


@pytest.mark.parametrize('name', ['', '.', '..', '../outside', r'..\outside',
                                  '/absolute', r'C:\outside', 'C:outside', 'trailing.', 'trailing '])
def test_invalid_id_is_rejected_before_path_use(tmp_path, name):
    with pytest.raises(ValueError, match='Invalid recording_id'):
        locations.resolve_recording(name, tmp_path, must_exist=False)


def test_shared_http_route_uses_the_same_identity_for_lease_and_handler(tmp_path):
    for parent in ('one', 'two'):
        (tmp_path / parent / 'walking').mkdir(parents=True)
    access = RecordingAccess()
    access.reserve(recording=locations.resolve_recording('walking', tmp_path / 'one'), task_id='writer')
    app = FastAPI()
    app.state.recording_access = access
    router = APIRouter(route_class=RecordingReadRoute)

    @router.get('/recordings/{recording_id}')
    def read(recording_id: str, recording_parent_directory: str | None = None):
        return {'path': str(recording_location(recording_id, recording_parent_directory).full_path)}

    app.include_router(router)
    with TestClient(app) as client:
        assert client.get('/recordings/walking', params={'recording_parent_directory': str(tmp_path / 'one')}).status_code == 409
        result = client.get('/recordings/walking', params={'recording_parent_directory': str(tmp_path / 'two')})
        assert result.status_code == 200
        assert Path(result.json()['path']) == (tmp_path / 'two' / 'walking').resolve()
        assert client.get('/recordings/missing', params={'recording_parent_directory': str(tmp_path)}).status_code == 404
        assert client.get('/recordings/C:outside', params={'recording_parent_directory': str(tmp_path)}).status_code == 400
    assert not access.readers
