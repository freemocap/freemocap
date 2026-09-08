"""Geometry fitness distinguishes missing detections from incompatible geometry."""

import numpy as np
import pytest
from numpy.typing import NDArray

from freemocap.core.tasks.calibration.camera_matching.matching_fitness import evaluate_geometry_fitness
from freemocap.core.tasks.calibration.camera_matching.matching_models import (
    CameraMatchingConfig,
    GeometryFitnessRequest,
    GeometryFitnessStatus,
)
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.triangulation.triangulator import Triangulator


def camera_rig() -> tuple[CameraModel, ...]:
    return tuple(
        CameraModel(
            id=f"camera {index}", index=index, image_size=(1280, 720),
            intrinsics=CameraIntrinsics(fx=900.0, fy=920.0, cx=640.0, cy=360.0, k1=-0.05),
            extrinsics=CameraExtrinsics(quaternion_wxyz=[1.0, 0.0, 0.0, 0.0], translation=translation),
        )
        for index, translation in enumerate(([0.0, 0.0, 0.0], [-700.0, 100.0, 0.0], [200.0, -600.0, 100.0]))
    )


def observations(cameras: tuple[CameraModel, ...]) -> NDArray[np.float64]:
    points = np.random.default_rng(17).uniform([-500.0, -300.0, 2500.0], [500.0, 300.0, 3500.0], (12, 10, 3))
    return Triangulator(cameras=list(cameras)).project(points.reshape(-1, 3)).reshape(len(cameras), 12, 10, 2)


def test_distorted_non_square_views_accept_correct_geometry() -> None:
    cameras = camera_rig()
    result = evaluate_geometry_fitness(request=GeometryFitnessRequest(
        cameras=cameras, pixels=observations(cameras), config=CameraMatchingConfig(),
    ))
    assert result.status is GeometryFitnessStatus.ACCEPTABLE
    assert all(item.valid_fraction == 1.0 and item.p90_error < 0.01 for item in result.cameras)


def test_wrong_assignment_is_poor_but_preserves_diagnostics() -> None:
    cameras = camera_rig()
    result = evaluate_geometry_fitness(request=GeometryFitnessRequest(
        cameras=cameras, pixels=observations(cameras)[[1, 0, 2]], config=CameraMatchingConfig(),
    ))
    assert result.status is GeometryFitnessStatus.POOR
    assert len(result.cameras) == len(cameras)


def test_missing_detections_do_not_imply_wrong_geometry() -> None:
    cameras = camera_rig()
    pixels = observations(cameras)
    pixels[1:] = np.nan
    result = evaluate_geometry_fitness(request=GeometryFitnessRequest(
        cameras=cameras, pixels=pixels, config=CameraMatchingConfig(),
    ))
    assert result.status is GeometryFitnessStatus.INSUFFICIENT


def test_isolated_missing_frame_does_not_reject_assignment() -> None:
    cameras = camera_rig()
    pixels = observations(cameras)
    pixels[:, 4] = np.nan
    result = evaluate_geometry_fitness(request=GeometryFitnessRequest(
        cameras=cameras, pixels=pixels, config=CameraMatchingConfig(),
    ))
    assert result.status is GeometryFitnessStatus.ACCEPTABLE


def test_invalid_coordinate_pair_fails_at_boundary() -> None:
    cameras = camera_rig()
    pixels = observations(cameras)
    pixels[0, 0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="both pixel"):
        GeometryFitnessRequest(cameras=cameras, pixels=pixels, config=CameraMatchingConfig())


def test_parallel_rays_cannot_pass_with_small_pixel_error() -> None:
    cameras = camera_rig()
    pixels = np.broadcast_to(np.array([640.0, 360.0]), (3, 12, 10, 2)).copy()
    result = evaluate_geometry_fitness(request=GeometryFitnessRequest(
        cameras=cameras, pixels=pixels, config=CameraMatchingConfig(),
    ))
    assert result.status is GeometryFitnessStatus.POOR
    assert all(item.valid_fraction == 0.0 for item in result.cameras)


def test_one_bad_tracking_frame_does_not_reject_healthy_window() -> None:
    cameras = camera_rig()
    pixels = observations(cameras)
    pixels[:, 4] = pixels[[1, 2, 0], 4]
    result = evaluate_geometry_fitness(request=GeometryFitnessRequest(
        cameras=cameras, pixels=pixels, config=CameraMatchingConfig(),
    ))
    assert result.status is GeometryFitnessStatus.ACCEPTABLE
