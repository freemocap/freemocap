"""Live reference offsets preserve projection and never accumulate across updates."""

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError
from skellyforge.core.math.geometry.spatial_vectors import Point

from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig
from freemocap.core.reconstruction.coordinate_conventions import RECONSTRUCTION_TO_CALIBRATION
from freemocap.core.reconstruction.reference_transform import ReferenceTransform
from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.tests.calibration.test_calibration_state_latch import build_loaded_tracker, FITTING_CAMERAS
from skellytracker.core.data_primitives.observation import Observation


def test_live_offset_replaces_resets_and_survives_source_reload(tmp_path: Path) -> None:
    source = build_loaded_tracker()._calibration
    assert source is not None
    path = tmp_path / "calibration.toml"
    source.dump_anipose_toml(path=path)
    original_file = path.read_bytes()
    tracker = CalibrationStateTracker.create_and_try_load(calibration_toml_path=path)
    tracker.bind_live_cameras(live_camera_indices=FITTING_CAMERAS)
    points = np.array([[100., -2000., 300.], [-200., -2500., 500.]])
    basis = RECONSTRUCTION_TO_CALIBRATION.matrix
    expected_projection = tracker.triangulator.project(points @ basis.T)
    offset = ReferenceTransform(matrix=(0., -1., 0., 125., 1., 0., 0., -80., 0., 0., 1., 42., 0., 0., 0., 1.))
    generation = tracker.generation
    assert tracker.set_reference_transform(reference_transform=offset)
    assert tracker.generation == generation + 1
    assert tracker.binding is None
    tracker.bind_live_cameras(live_camera_indices=FITTING_CAMERAS)
    transformed_points = offset.to_transform().apply(points=Point.from_prevalidated_array(array=points)).array
    np.testing.assert_allclose(tracker.triangulator.project(transformed_points @ basis.T), expected_projection, atol=1e-8)
    cameras = tracker.triangulator.cameras
    assert not tracker.set_reference_transform(reference_transform=offset)
    assert tracker.generation == generation + 1
    assert tracker._try_load_from_path(path=path)
    for before, after in zip(cameras, tracker.triangulator.cameras, strict=True):
        np.testing.assert_allclose(before.extrinsics.translation, after.extrinsics.translation)
        assert before.id == after.id
    replacement = ReferenceTransform(matrix=(1., 0., 0., -60., 0., 1., 0., 20., 0., 0., 1., 0., 0., 0., 0., 1.))
    assert tracker.set_reference_transform(reference_transform=replacement)
    replacement_points = replacement.to_transform().apply(points=Point.from_prevalidated_array(array=points)).array
    np.testing.assert_allclose(tracker.triangulator.project(replacement_points @ basis.T), expected_projection, atol=1e-8)
    assert tracker.try_angulate(
        frame_number=0,
        frame_observations_by_camera={
            "cam0": Observation(frame_number=0, image_size=(720, 1280)),
        },
        max_reprojection_error_px=10.0,
    ) is None
    assert tracker.set_reference_transform(reference_transform=None)
    np.testing.assert_allclose(tracker.triangulator.project(points @ basis.T), expected_projection, atol=1e-8)
    assert path.read_bytes() == original_file


def test_pending_offset_applies_when_calibration_is_loaded(tmp_path: Path) -> None:
    source = build_loaded_tracker()._calibration
    assert source is not None
    path = tmp_path / "calibration.toml"
    source.dump_anipose_toml(path=path)
    config = RealtimeAggregatorNodeConfig.model_validate({"reference_transform": {
        "matrix": [1, 0, 0, 200, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    }})
    restored = RealtimeAggregatorNodeConfig.model_validate_json(config.model_dump_json())
    tracker = CalibrationStateTracker()
    assert not tracker.set_reference_transform(reference_transform=restored.reference_transform)
    assert tracker.set_source_path(calibration_toml_path=path)
    np.testing.assert_allclose(tracker.triangulator.cameras[0].extrinsics.translation,
        source.cameras[0].extrinsics.translation - RECONSTRUCTION_TO_CALIBRATION.matrix @ np.array([200., 0., 0.]))


def test_live_config_rejects_nonrigid_offset() -> None:
    with pytest.raises(ValidationError):
        RealtimeAggregatorNodeConfig.model_validate({"reference_transform": {"matrix": [0.] * 16}})
