from freemocap.core.recording.recording_access import RecordingAccess
"""Playback projects canonical samples without executing the scientific pipeline."""

from pathlib import Path

import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from freemocap.api.http.playback.playback_router import playback_router
from freemocap.api.http.playback.playback_router import video_stream_url
from urllib.parse import parse_qs, urlsplit

from freemocap.core.recording.playback_queries import (
    playback_manifest,
)
from freemocap.core.recording.playback_queries import recording_view
from freemocap.core.recording.result_processing.observation_publication import (
    publish_posthoc_observations,
)
from freemocap.core.recording.result_processing.observation_inputs import (
    ObservationRecordingRequest,
)
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.test_reconstruction_checkpoints import publication


def test_replacing_video_changes_playback_url_without_adding_output_files(tmp_path: Path) -> None:
    video = tmp_path / "camera video.mp4"
    video.write_bytes(b"first")
    parameters = {"source": "annotated", "recording_parent_directory": str(tmp_path)}
    before = video_stream_url(recording_id="recording name", path=video, parameters=parameters)
    assert video_stream_url(recording_id="recording name", path=video, parameters=parameters) == before
    temporary = tmp_path / "temporary.mp4"
    temporary.write_bytes(b"other")
    temporary.replace(video)
    after = video_stream_url(recording_id="recording name", path=video, parameters=parameters)
    assert before != after
    query = parse_qs(urlsplit(after).query)
    assert query["source"] == ["annotated"]
    assert query["recording_parent_directory"] == [str(tmp_path)]
    assert list(tmp_path.iterdir()) == [video]


def test_playback_manifest_uses_live_model_wire_format(
    publication: ObservationRecordingRequest, tmp_path: Path
) -> None:
    publish_posthoc_observations(publication)
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    manifest = playback_manifest(structure.data_parquet_path)
    assert manifest.runs[0].models[0].model_id == publication.models[0].model_id
    assert manifest.runs[0].models[0].segments
    assert manifest.runs[0].model_sources == {
        item.definition.source_name: item.definition.model_id
        for item in publication.reconstructions
    }
    encoded = json.loads(manifest.model_dump_json())
    assert encoded["runs"][0]["models"] == [
        json.loads(json.dumps(model.to_cbor_message()))
        for model in manifest.runs[0].models
    ]



def test_parquet_download_preserves_bytes_and_checks_revision(
    publication: ObservationRecordingRequest, tmp_path: Path,
) -> None:
    publish_posthoc_observations(publication)
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    manifest = playback_manifest(structure.data_parquet_path)
    app = FastAPI()
    app.state.recording_access = RecordingAccess()
    app.include_router(playback_router)
    with TestClient(app) as client:
        params = {
            "recording_parent_directory": str(tmp_path),
            "revision": manifest.revision,
        }
        response = client.get("/playback/recording/parquet", params=params)
        assert response.status_code == 200
        assert response.content == structure.data_parquet_path.read_bytes()
        assert response.headers["etag"] == f'"{manifest.revision}"'
        assert response.headers["cache-control"] == "no-store"
        publish_posthoc_observations(publication)
        assert client.get("/playback/recording/parquet", params=params).status_code == 409


def test_open_playback_snapshot_allows_atomic_publication(
    publication: ObservationRecordingRequest, tmp_path: Path
) -> None:
    publish_posthoc_observations(publication)
    path = RecordingStructure(
        base_directory=tmp_path, recording_name="recording"
    ).data_parquet_path
    with recording_view(path) as previous:
        publish_posthoc_observations(publication)
        assert previous.parquet.read().num_rows > 0
        assert playback_manifest(path).revision != previous.revision


def test_playback_api_revision_and_validation(
    publication: ObservationRecordingRequest, tmp_path: Path
) -> None:
    publish_posthoc_observations(publication)
    app = FastAPI()
    app.state.recording_access = RecordingAccess()
    app.include_router(playback_router)
    with TestClient(app) as client:
        params = dict(recording_parent_directory=str(tmp_path))
        response = client.get("/playback/recording/manifest", params=params)
        assert response.status_code == 200
        params["revision"] = response.json()["revision"]
        assert client.get("/playback/recording/parquet", params=params).status_code == 200
        params["revision"] = "stale"
        assert client.get("/playback/recording/parquet", params=params).status_code == 409
        assert client.post("/playback/recording/window", params=params).status_code == 404
