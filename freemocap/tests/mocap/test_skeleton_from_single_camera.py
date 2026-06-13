"""Tests for the single-camera (no-triangulation) skeleton-building path."""

from pathlib import Path

import numpy as np
from skellyforge.skellymodels.managers.human import Human
from skellyforge.skellymodels.models.tracking_model_info import MediapipeModelInfo, RTMPoseModelInfo
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder
from skellytracker.trackers.base_tracker.point_cloud import PointCloud
from skellytracker.trackers.mediapipe_tracker import MediapipeObservation
from skellytracker.trackers.mediapipe_tracker.names_and_connections import MEDIAPIPE_HOLISTIC_DEFINITION
from skellytracker.trackers.rtmpose_tracker.names_and_connections import RTMPOSE_WHOLEBODY_DEFINITION
from skellytracker.trackers.rtmpose_tracker.rtmpose_observation import RTMPoseObservation

from freemocap.core.tasks.mocap.mocap_helpers.skeleton_from_mediapipe_observations import (
    _flat_3d_from_pixels,
    _model_info_for_recorders,
    skeleton_from_mediapipe_observation_recorders,
)

IMAGE_SIZE = (480, 640)  # (height, width)


def _synthetic_2d_array(n_frames: int, n_points: int, seed: int) -> np.ndarray:
    """(n_frames, n_points, 2) pixel positions: small per-frame jitter around fixed base positions."""
    rng = np.random.default_rng(seed)
    base = rng.uniform(low=[100.0, 50.0], high=[540.0, 430.0], size=(n_points, 2))
    jitter = rng.normal(scale=2.0, size=(n_frames, n_points, 2))
    return base[np.newaxis, :, :] + jitter


def _rtmpose_recorder(n_frames: int) -> BaseRecorder:
    names = RTMPOSE_WHOLEBODY_DEFINITION.tracked_points
    data2d = _synthetic_2d_array(n_frames=n_frames, n_points=len(names), seed=1)
    recorder = BaseRecorder()
    for frame_idx in range(n_frames):
        xyz = np.column_stack([data2d[frame_idx], np.zeros(len(names))])
        cloud = PointCloud(names=names, xyz=xyz, visibility=np.ones(len(names)))
        recorder.add_observation(
            RTMPoseObservation(frame_number=frame_idx, image_size=IMAGE_SIZE, points=cloud)
        )
    return recorder


def _mediapipe_recorder(n_frames: int) -> BaseRecorder:
    names = MEDIAPIPE_HOLISTIC_DEFINITION.tracked_points
    data2d = _synthetic_2d_array(n_frames=n_frames, n_points=len(names), seed=2)
    recorder = BaseRecorder()
    for frame_idx in range(n_frames):
        xyz = np.column_stack([data2d[frame_idx], np.zeros(len(names))])
        cloud = PointCloud(names=names, xyz=xyz, visibility=np.ones(len(names)))
        recorder.add_observation(
            MediapipeObservation(frame_number=frame_idx, image_size=IMAGE_SIZE, points=cloud)
        )
    return recorder


def test_flat_3d_from_pixels_is_centered_and_flat() -> None:
    data2d = _synthetic_2d_array(n_frames=30, n_points=10, seed=3)

    result = _flat_3d_from_pixels(data2d=data2d, image_size=IMAGE_SIZE)

    assert result.shape == (30, 10, 3)
    assert np.all(result[..., 2] == 0)
    # Each frame is centered on its own centroid.
    assert np.allclose(result[..., :2].mean(axis=1), 0.0, atol=1e-9)


def test_model_info_for_recorders_rtmpose() -> None:
    recorder = _rtmpose_recorder(n_frames=2)

    model_info = _model_info_for_recorders({"cam_0": recorder})

    assert model_info.name == RTMPoseModelInfo().name


def test_model_info_for_recorders_mediapipe() -> None:
    recorder = _mediapipe_recorder(n_frames=2)

    model_info = _model_info_for_recorders({"cam_0": recorder})

    assert model_info.name == MediapipeModelInfo().name


def test_single_camera_rtmpose_skeleton(tmp_path: Path) -> None:
    recorder = _rtmpose_recorder(n_frames=30)

    skeleton = skeleton_from_mediapipe_observation_recorders(
        observation_recorders={"cam_0": recorder},
        path_to_calibration_toml=None,
        path_to_output_data_folder=tmp_path,
    )

    assert isinstance(skeleton, Human)
    assert any(tmp_path.glob("*_skeleton_3d.npy"))
    assert (tmp_path / "freemocap_data_by_frame.csv").exists()


def test_single_camera_mediapipe_skeleton(tmp_path: Path) -> None:
    recorder = _mediapipe_recorder(n_frames=30)

    skeleton = skeleton_from_mediapipe_observation_recorders(
        observation_recorders={"cam_0": recorder},
        path_to_calibration_toml=None,
        path_to_output_data_folder=tmp_path,
    )

    assert isinstance(skeleton, Human)
    assert any(tmp_path.glob("*_skeleton_3d.npy"))


def test_multi_camera_requires_calibration_path(tmp_path: Path) -> None:
    recorder_a = _rtmpose_recorder(n_frames=5)
    recorder_b = _rtmpose_recorder(n_frames=5)

    try:
        skeleton_from_mediapipe_observation_recorders(
            observation_recorders={"cam_0": recorder_a, "cam_1": recorder_b},
            path_to_calibration_toml=None,
            path_to_output_data_folder=tmp_path,
        )
        raise AssertionError("Expected ValueError for missing calibration with 2+ cameras")
    except ValueError as exc:
        assert "calibration" in str(exc)
