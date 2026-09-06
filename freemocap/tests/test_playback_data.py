"""Playback projects canonical samples without executing the scientific pipeline."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from freemocap.api.http.playback.playback_router import playback_router
from freemocap.core.recording.parquet_storage.parquet_writer import (
    publish_recording,
    recording_write_lock,
)
from freemocap.tests.test_recording_store import metadata_fixture, sample_batch

from freemocap.core.recording.playback_queries import (
    PlaybackWindowRequest,
    StalePlaybackRevision,
    playback_manifest,
    playback_window,
)
from freemocap.core.recording.playback_queries import recording_view
from freemocap.core.recording.result_processing.observation_publication import (
    publish_posthoc_observations,
)
from freemocap.core.recording.result_processing.observation_inputs import (
    ObservationRecordingRequest,
)
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.test_reconstruction_checkpoints import publication


def test_playback_manifest_and_bounded_samples(
    publication: ObservationRecordingRequest, tmp_path: Path
) -> None:
    publish_posthoc_observations(publication)
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    manifest = playback_manifest(structure.data_parquet_path)
    assert manifest.runs[0].models[0].model_id == publication.models[0].model_id
    assert manifest.runs[0].models[0].segments
    assert manifest.model_dump_json()
    request = PlaybackWindowRequest(
        run_id=0,
        revision=manifest.revision,
        sensor_groups=("mocap",),
        start_s=0.0,
        end_s=0.02,
    )
    first = playback_window(path=structure.data_parquet_path, request=request)
    assert first.channels and all(item.frame_numbers == (0,) for item in first.channels)
    assert first.model_dump_json()
    second = playback_window(
        path=structure.data_parquet_path,
        request=request.model_copy(update={"start_s": 0.02, "end_s": 0.1}),
    )
    landmarks = next(
        item
        for item in second.channels
        if item.channel.kind == ChannelKind.LANDMARKS_3D
    )
    assert landmarks.frame_numbers == (1,)
    assert all(value is None for value in landmarks.values)
    publish_posthoc_observations(publication)
    with pytest.raises(StalePlaybackRevision):
        playback_window(path=structure.data_parquet_path, request=request)


def test_playback_rejects_unbounded_queries() -> None:
    with pytest.raises(ValueError, match="at most three"):
        PlaybackWindowRequest(
            run_id=0, revision="revision", sensor_groups=("mocap",), start_s=0, end_s=60
        )


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


def test_playback_preserves_different_group_rates(tmp_path: Path) -> None:
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    with recording_write_lock(structure=structure):
        publish_recording(
            structure=structure,
            metadata=metadata_fixture(),
            batches=[
                sample_batch(group="mocap", count=2, fps=30.0),
                sample_batch(group="eye", count=8, fps=120.0),
            ],
        )
    manifest = playback_manifest(structure.data_parquet_path)
    result = playback_window(
        path=structure.data_parquet_path,
        request=PlaybackWindowRequest(
            run_id=0,
            revision=manifest.revision,
            sensor_groups=("mocap", "eye"),
            start_s=0,
            end_s=0.1,
        ),
    )
    counts = {
        item.channel.sensor_group: len(item.frame_numbers) for item in result.channels
    }
    assert counts == {"mocap": 2, "eye": 8}


def test_playback_api_revision_and_validation(
    publication: ObservationRecordingRequest, tmp_path: Path
) -> None:
    publish_posthoc_observations(publication)
    app = FastAPI()
    app.include_router(playback_router)
    with TestClient(app) as client:
        params = dict(recording_parent_directory=str(tmp_path))
        response = client.get("/playback/recording/manifest", params=params)
        assert response.status_code == 200
        request = dict(
            run_id=0,
            revision=response.json()["revision"],
            sensor_groups=["mocap"],
            start_s=0,
            end_s=0.1,
        )
        assert (
            client.post(
                "/playback/recording/window", params=params, json=request
            ).status_code
            == 200
        )
        request["revision"] = "stale"
        assert (
            client.post(
                "/playback/recording/window", params=params, json=request
            ).status_code
            == 409
        )
        request["end_s"] = 60
        assert (
            client.post(
                "/playback/recording/window", params=params, json=request
            ).status_code
            == 422
        )
