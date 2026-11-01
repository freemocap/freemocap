"""Canonical recording resources work independently of playback composition."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.recordings.resources_router import recordings_router
from freemocap.api.http.playback.playback_router import playback_router
from freemocap.core.recording.recording_access import RecordingAccess
from freemocap.tests.test_wide_csv_export import recording_processing  # noqa: F401


def api():
    app = FastAPI()
    app.state.recording_access = RecordingAccess()
    app.include_router(recordings_router, prefix='/freemocap')
    app.include_router(playback_router, prefix='/freemocap')
    return app


def test_catalog_exposes_resources_and_preserves_hidden_compatibility():
    schema = api().openapi()
    paths = schema['paths']
    assert not any('/playback/' in path and '/recordings/' not in path for path in paths)
    assert paths['/freemocap/recordings']['get']['tags'] == ['Recordings']
    assert paths['/freemocap/recordings/{recording_id}/videos']['get']['tags'] == ['Recording media']
    assert paths['/freemocap/recordings/{recording_id}/playback/bundle']['get']['tags'] == ['Playback']
    operations = [value['operationId'] for path in paths.values() for value in path.values()]
    assert len(set(operations)) == len(operations)


def test_custom_openapi_preserves_ordered_capability_descriptions():
    from freemocap.app.app import _customize_openapi
    from freemocap.api.openapi_tags import OPENAPI_TAGS
    app = api()
    _customize_openapi(app)
    assert app.openapi()['tags'] == OPENAPI_TAGS


def test_run_resources_are_revision_bound_without_playback(recording_processing, monkeypatch):  # noqa: F811 - shared pytest fixture
    structure, _ = recording_processing
    from freemocap.api.http.playback import playback_router as playback

    def forbidden(*args, **kwargs):
        raise AssertionError('General recording queries must not compose playback')

    monkeypatch.setattr(playback, 'playback_manifest', forbidden)
    base = f'/freemocap/recordings/{structure.recording_name}'
    params = {'recording_parent_directory': str(structure.base_directory)}
    with TestClient(api()) as client:
        resource = client.get(base, params=params)
        assert resource.status_code == 200
        assert resource.json()['resources']['saved_results']
        runs = client.get(resource.json()['links']['runs'])
        assert runs.status_code == 200
        selected = runs.json()['selected_run_id']
        channels = client.get(f'{base}/runs/{selected}/channels', params=params)
        assert channels.status_code == 200
        assert channels.json()['revision'] == runs.json()['revision']
        assert channels.json()['channels']
        assert client.get(f'{base}/runs/999/channels', params=params).status_code == 404
        params['revision'] = runs.json()['revision']
        saved = client.get(f'{base}/parquet', params=params)
        assert saved.status_code == 200
        assert saved.content == structure.data_parquet_path.read_bytes()
        params['revision'] = 'stale'
        assert client.get(f'{base}/parquet', params=params).status_code == 409


def test_recording_without_processed_results_remains_addressable(tmp_path):
    folder = tmp_path / 'unprocessed'
    folder.mkdir()
    params = {'recording_parent_directory': str(tmp_path)}
    with TestClient(api()) as client:
        base = '/freemocap/recordings/unprocessed'
        assert client.get(base, params=params).status_code == 200
        assert client.get(base + '/runs', params=params).json() == {'revision': None, 'selected_run_id': None, 'runs': []}
        assert client.get(base + '/parquet', params=params).status_code == 404


def test_canonical_video_read_preserves_range_and_source_selection(tmp_path):
    # Reading an existing video needs no detector, saved result or rendering model.
    folder = tmp_path / 'clip' / 'synchronized_videos'
    folder.mkdir(parents=True)
    payload = b'video-content-for-range-contract'
    (folder / 'camera 1.mp4').write_bytes(payload)
    with TestClient(api()) as client:
        response = client.get('/freemocap/recordings/clip/videos/camera%201.mp4',
                              params={'recording_parent_directory': str(tmp_path), 'source': 'synchronized'},
                              headers={'Range': 'bytes=3-9'})
        assert response.status_code == 206
        assert response.content == payload[3:10]
        assert response.headers['content-range'] == f'bytes 3-9/{len(payload)}'
