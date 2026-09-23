"""Production readers consume real pipeline outputs; no inference is mocked here."""

import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import numpy as np
import pytest

from freemocap.api.http.playback.playback_router import playback_router
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.playback_queries import playback_manifest
from freemocap.core.recording.recording_access import RecordingAccess
from freemocap.core.recording.result_processing.saved_reconstruction import (
    SavedPointPolicy, SavedReconstructionRequest, read_saved_reconstruction,
)
from freemocap.core.recording.sample_encoding.reconstruction_samples import (
    ReconstructionSourceDefinition, model_source_name,
)
from freemocap.core.skeletons.standard_human_skeleton import STANDARD_HUMAN_MODEL_ID
from freemocap.core.tasks.calibration.shared.calibration_paths import find_recording_calibration
from freemocap.core.tasks.calibration.shared.loaded_calibration import LoadedCalibration
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.tests.prepare_recording_dataset import file_digest

pytestmark = pytest.mark.e2e


def assert_json_matches(actual, expected, path="manifest"):
    """Report the differing field instead of dumping the entire human model."""
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys(), path
        for key in expected:
            assert_json_matches(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert len(actual) == len(expected), path
        for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
            assert_json_matches(left, right, f"{path}[{index}]")
    else:
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"


@pytest.fixture(scope="module")
def saved(prepared_reference):
    metadata = read_metadata(path=prepared_reference.data_parquet_path)
    manifest = playback_manifest(prepared_reference.data_parquet_path)
    run = metadata.runs[metadata.selected_run_id]
    playback = next(item for item in manifest.runs if item.run_id == metadata.selected_run_id)
    return metadata, run, manifest, playback


def test_reference_playback_frame_grid_and_human_model(prepared_reference, saved):
    metadata, run, manifest, playback = saved
    assert manifest.recording_id == prepared_reference.recording_name
    assert manifest.selected_run_id == metadata.selected_run_id
    assert playback.model_sources[model_source_name(STANDARD_HUMAN_MODEL_ID)] == STANDARD_HUMAN_MODEL_ID
    human = next(model for model in playback.models if model.model_id == STANDARD_HUMAN_MODEL_ID)
    assert human.segments
    assert len(playback.media) == 3
    assert len({media.timeline.source for media in playback.media}) == 3
    for media in playback.media:
        assert media.timeline.frame_numbers == tuple(range(222))
        np.testing.assert_allclose(media.timeline.timestamps_s, np.arange(222) / 6, atol=1e-6, rtol=0)
        assert media.nominal_fps == pytest.approx(6)
    for group in run.sensor_groups.values():
        assert group.sample_count == 222


def test_reference_human_inputs_and_matching_scale_fit(prepared_reference, saved):
    metadata, run, manifest, playback = saved
    definition = ReconstructionSourceDefinition.model_validate(
        run.sources[model_source_name(STANDARD_HUMAN_MODEL_ID)].definition)
    policy = (SavedPointPolicy.IDENTITY if definition.point_kind == ChannelKind.RAW_KEYPOINTS_3D
              else SavedPointPolicy.FILTERED)
    channels = [channel for channel in run.channels
                if channel.source == definition.tracker and channel.kind == definition.point_kind]
    assert len(channels) == 1
    channel = channels[0]
    loaded = read_saved_reconstruction(SavedReconstructionRequest(
        structure=prepared_reference, run_id=metadata.selected_run_id, sensor_group=channel.sensor_group,
        point_source=definition.tracker, model_id=STANDARD_HUMAN_MODEL_ID,
        point_policy=policy, compute_center_of_mass=False))
    assert loaded.points.frames == tuple(range(222))
    np.testing.assert_allclose(loaded.points.timestamps_s, np.arange(222) / 6, atol=1e-6, rtol=0)
    assert loaded.points.values.shape == (222, len(channel.names), 3)
    assert loaded.numerical_input.keypoint_names == channel.names
    assert np.isfinite(loaded.points.values).all(axis=2).any(), "Human input is entirely missing"
    assert not np.isinf(loaded.points.values).any()
    assert not loaded.points.values.flags.writeable
    assert loaded.fit.fit is not None, "Real human recording has no fitted scale"
    assert loaded.fit.inputs == loaded.numerical_input.fit_inputs(loaded.numerical_input.bundles[0])


def test_reference_calibration_and_alignment_provenance(prepared_reference, saved):
    metadata, run, manifest, playback = saved
    path = find_recording_calibration(recording_folder=prepared_reference.full_path)
    assert path is not None
    calibration = LoadedCalibration.from_path(path)
    assert len(calibration.cameras) == 3
    assert calibration.metadata.board.squares_x == 7
    assert calibration.metadata.board.squares_y == 5
    assert np.isfinite(calibration.metadata.reprojection_error_px)
    assert run.calibration_updates, "Processed alignment provenance is missing"
    assert playback.calibration_updates == run.calibration_updates
    for update in playback.calibration_updates.values():
        assert update.transformations
    # Reading again must not apply pending alignment transformations or mutate files.
    assert playback_manifest(prepared_reference.data_parquet_path).model_dump() == manifest.model_dump()
    assert LoadedCalibration.from_path(path) == calibration


def test_reference_playback_http_bytes_and_revision(prepared_reference, saved):
    metadata, run, manifest, playback = saved
    app = FastAPI()
    app.state.recording_access = RecordingAccess()
    app.include_router(playback_router)
    base = f"/playback/{prepared_reference.recording_name}"
    params = {"recording_parent_directory": str(prepared_reference.base_directory)}
    with TestClient(app) as client:
        response = client.get(f"{base}/manifest", params=params)
        assert response.status_code == 200, response.text
        payload = response.json()
        for api_run in payload["runs"]:
            originals = [media for media in api_run["media"] if media["video_source"] == "synchronized"]
            annotated = [media for media in api_run["media"] if media["video_source"] == "annotated"]
            assert len(annotated) == len(originals) == 3
            by_source = {media["timeline"]["source"]: media for media in originals}
            assert {media["timeline"]["source"] for media in annotated} == set(by_source)
            for media in annotated:
                original = by_source[media["timeline"]["source"]]
                assert media["timeline"] == original["timeline"]
                assert media["nominal_fps"] == original["nominal_fps"]
                assert media["video_filename"] != original["video_filename"]
            api_run["media"] = originals
        assert_json_matches(payload, json.loads(manifest.model_dump_json()))
        response = client.get(f"{base}/parquet", params=dict(params, revision=manifest.revision))
        assert response.status_code == 200
        assert hashlib.sha256(response.content).hexdigest() == file_digest(prepared_reference.data_parquet_path)
        assert response.headers["etag"] == f'"{manifest.revision}"'
        assert client.get(f"{base}/parquet", params=dict(params, revision="stale")).status_code == 409
