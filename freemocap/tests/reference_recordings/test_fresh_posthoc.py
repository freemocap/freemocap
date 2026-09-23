"""Fresh calibration -> RTMPose -> reconstruction through production pipelines."""

from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.sample_encoding.reconstruction_samples import model_source_name
from freemocap.core.skeletons.standard_human_skeleton import STANDARD_HUMAN_MODEL_ID
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.tests.inspect_recording_datasets import inspect_video
from freemocap.tests.pipelines.real_data_numeric_bounds import (
    MAX_REPROJECTION_ERROR_PX, MIN_OBSERVATIONS_USED, MAX_REJECTED_OBSERVATION_FRACTION,
)
from freemocap.tests.prepare_recording_dataset import file_digest, prepare
from freemocap.tests.recording_datasets import TEST_DATA


def check_fresh_outputs(recording: Path, result: dict) -> None:
    assert result["calibration_task"]["status"] == "complete"
    assert result["mocap_task"]["status"] == "complete"
    calibration_path = recording / result["calibration_filename"]
    assert Path(result["mocap_config"]["calibration_toml_path"]) == calibration_path
    calibration = CalibrationResult.load_toml(calibration_path)
    assert len(calibration.cameras) == 3
    assert 0 <= calibration.reprojection_error_px < MAX_REPROJECTION_ERROR_PX
    assert calibration.n_observations_used >= MIN_OBSERVATIONS_USED
    assert calibration.n_observations_rejected / calibration.n_observations_used <= MAX_REJECTED_OBSERVATION_FRACTION
    # All three production save destinations must belong to this isolated run.
    application_calibrations = recording.parents[1] / "app-data" / "calibrations"
    for filename in (calibration_path.name, "last_successful_camera_calibration.toml"):
        assert file_digest(application_calibrations / filename) == file_digest(calibration_path)

    sources = sorted((recording / "synchronized_videos").glob("*.mp4"))
    annotated = sorted((recording / "annotated_videos").glob("*.mp4"))
    assert len(sources) == len(annotated) == 3
    for source in sources:
        output = recording / "annotated_videos" / f"{source.name}.annotated.mp4"
        original, annotation = inspect_video(source), inspect_video(output)
        assert annotation.decoded_frames == original.decoded_frames == 222
        assert (annotation.width, annotation.height) == (original.width, original.height)
        assert annotation.nominal_fps == original.nominal_fps

    parquet = recording / f"{recording.name}_data.parquet"
    metadata = read_metadata(path=parquet)
    run = metadata.runs[metadata.selected_run_id]
    assert metadata.recording_id == recording.name
    assert run.calibration_updates
    assert all(group.sample_count == 222 for group in run.sensor_groups.values())
    human = model_source_name(STANDARD_HUMAN_MODEL_ID)
    assert STANDARD_HUMAN_MODEL_ID in run.models
    # Select the human specifically: finite board data cannot satisfy these checks.
    for kind, components in (("LANDMARKS_3D", ("x", "y", "z")),
                             ("ROTATIONS_WORLD", ("w", "x", "y", "z"))):
        table = pq.read_table(parquet, filters=[("run_id", "=", metadata.selected_run_id),
                                               ("source", "=", human), ("channel", "=", kind)])
        rows = table.to_pylist()
        assert {row["frame_number"] for row in rows} == set(range(222)), kind
        channel = next(channel for channel in run.channels if channel.source == human and channel.kind == kind)
        assert {row["name"] for row in rows} == set(channel.names)
        vectors = {}
        for row in rows:
            key = (row["sensor_group"], row["frame_number"], row["name"])
            vector = vectors.setdefault(key, {})
            assert row["component"] not in vector, f"Duplicate {kind} component"
            vector[row["component"]] = np.nan if row["value"] is None else row["value"]
        assert all(set(vector) == set(components) for vector in vectors.values())
        values = np.array([[vector[component] for component in components] for vector in vectors.values()])
        assert not np.isinf(values).any(), kind
        complete = values[np.isfinite(values).all(axis=1)]
        assert len(complete), f"No finite human {kind} vectors"
        if kind == "ROTATIONS_WORLD":
            np.testing.assert_allclose(np.linalg.norm(complete, axis=1), 1.0, atol=1e-6)


@pytest.mark.e2e
@pytest.mark.slow
def test_fresh_calibration_and_mocap_publish_current_recording():
    base = Path.home() / "freemocap_data"
    calls = []

    def validate(recording: Path, result: dict) -> None:
        calls.append(recording)
        check_fresh_outputs(recording, result)

    prepare(TEST_DATA, recordings_root=base / "recordings", prepared_root=base / "testing" / "prepared",
            fresh=True, timeout=1800.0, validate_fresh=validate)
    assert len(calls) == 1, "A cached result must not satisfy the producer test"
    assert not (base / "testing" / "prepared" / TEST_DATA.name / "scratch").exists()
