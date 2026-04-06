"""Shared ground plane alignment for camera calibration.

Provides GroundPlaneResult (the output of any ground plane estimation method)
and apply_groundplane_to_cameras (transforms camera extrinsics to a new world
frame defined by the ground plane).

Used by both charuco-based and feet-based ground plane estimation.
"""

import logging
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation

from freemocap.core.calibration.shared.calibration_models import (
    CameraExtrinsics,
    CameraModel,
)

logger = logging.getLogger(__name__)


@dataclass
class GroundPlaneResult:
    """Result of ground plane estimation from any method."""

    origin: NDArray[np.float64]  # (3,) world origin position
    rotation_matrix: NDArray[np.float64]  # (3,3) [x_hat | y_hat | z_hat]
    method: str  # "charuco" or "feet"


def apply_groundplane_to_cameras(
    cameras: list[CameraModel],
    ground_plane: GroundPlaneResult,
) -> list[CameraModel]:
    """Apply ground plane transform to camera extrinsics.

    Shifts the world origin to ground_plane.origin and rotates the world
    frame so that the ground plane's basis vectors become the new axes.

    Args:
        cameras: Calibrated camera models.
        ground_plane: Estimated ground plane (origin + rotation).

    Returns:
        Camera models with extrinsics adjusted to the new world frame.
    """
    origin = ground_plane.origin
    R_ground_to_world = ground_plane.rotation_matrix

    result: list[CameraModel] = []
    for cam in cameras:
        R_cam = cam.extrinsics.rotation_matrix
        t_cam = cam.extrinsics.translation

        # Shift origin, then rotate
        t_delta = R_cam @ origin
        t_new = t_cam + t_delta

        # Compose with ground-to-world rotation
        R_new = R_cam @ R_ground_to_world

        quat_xyzw = Rotation.from_matrix(R_new).as_quat()
        quat_wxyz = np.array(
            [quat_xyzw[3], quat_xyzw[0], quat_xyzw[1], quat_xyzw[2]],
            dtype=np.float64,
        )

        result.append(
            CameraModel(
                name=cam.name,
                image_size=cam.image_size,
                intrinsics=cam.intrinsics,
                extrinsics=CameraExtrinsics(
                    quaternion_wxyz=quat_wxyz,
                    translation=t_new,
                ),
            )
        )

    logger.info(
        f"Ground plane alignment complete (method: {ground_plane.method})"
    )
    return result


def groundplane_metadata(
    ground_plane: GroundPlaneResult,
    recording_id: str,
) -> dict:
    """Return metadata dict to merge into calibration TOML."""
    return {
        "groundplane_applied": True,
        "groundplane_method": ground_plane.method,
        "groundplane_recording_id": recording_id,
    }
