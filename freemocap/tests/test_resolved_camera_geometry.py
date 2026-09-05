"""Saved geometry preserves the projection used by triangulation."""

import numpy as np

from freemocap.core.recording.resolved_camera_geometry import ResolvedCameraGeometry
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


def test_camera_geometry_json_round_trip_preserves_projection() -> None:
    camera = CameraModel(
        id="camera",
        index=0,
        image_size=(640, 480),
        intrinsics=CameraIntrinsics(fx=800.0, fy=810.0, cx=320.0, cy=240.0, k1=0.01),
        extrinsics=CameraExtrinsics(
            quaternion_wxyz=np.array([1.0, 0.0, 0.0, 0.0]),
            translation=np.array([100.0, 20.0, 500.0]),
        ),
    )
    descriptor = ResolvedCameraGeometry.from_camera(camera)
    restored = ResolvedCameraGeometry.model_validate_json(
        descriptor.model_dump_json()
    ).to_camera()
    np.testing.assert_allclose(restored.projection_matrix, camera.projection_matrix)
    np.testing.assert_allclose(
        restored.intrinsics.to_dist_coeffs_5(), camera.intrinsics.to_dist_coeffs_5()
    )
    np.testing.assert_allclose(
        restored.world_position, camera.extrinsics.world_position
    )
    camera.extrinsics.translation[0] = -1000.0
    assert descriptor.world_to_camera_translation_mm[0] == 100.0
