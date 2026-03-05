"""Post-processing transforms for calibrated cameras.

Pin camera 0 to origin, align charuco board as ground plane,
compute world-frame camera positions and orientations.
"""

import logging

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation

from freemocap.core.calibration.shared.calibration_models import CameraModel, CameraExtrinsics, \
    CharucoCornersObservation, CharucoBoardDefinition
from freemocap.core.calibration.shared.groundplane_math import find_still_charuco_frame, compute_board_basis_vectors

logger = logging.getLogger(__name__)


# =============================================================================
# PIN CAMERA TO ORIGIN
# =============================================================================


def pin_camera_to_origin(
    *,
    cameras: list[CameraModel],
    camera_index: int = 0,
) -> list[CameraModel]:
    """Re-express all camera extrinsics relative to the specified camera.

    After this transform, the target camera has identity rotation and zero
    translation (it sits at the world origin looking along +Z).

    Args:
        cameras: List of camera models with extrinsics.
        camera_index: Index of the camera to place at the origin.

    Returns:
        New list of CameraModel with adjusted extrinsics.
    """
    if camera_index < 0 or camera_index >= len(cameras):
        raise IndexError(
            f"camera_index {camera_index} out of range for {len(cameras)} cameras"
        )

    ref_cam = cameras[camera_index]
    R0 = ref_cam.extrinsics.rotation_matrix
    t0 = ref_cam.extrinsics.translation

    result: list[CameraModel] = []
    for cam in cameras:
        R_i = cam.extrinsics.rotation_matrix
        t_i = cam.extrinsics.translation

        # New rotation: R_i_new = R_i @ R0^T
        R_new = R_i @ R0.T

        # New translation: t_new = t_i + R_i @ R0^T @ (-t0)
        t_new = t_i + R_i @ R0.T @ (-t0)

        # Convert to quaternion wxyz
        quat_xyzw = Rotation.from_matrix(R_new).as_quat()
        quat_wxyz = np.array(
            [quat_xyzw[3], quat_xyzw[0], quat_xyzw[1], quat_xyzw[2]],
            dtype=np.float64,
        )

        new_extrinsics = CameraExtrinsics(
            quaternion_wxyz=quat_wxyz,
            translation=t_new,
        )

        result.append(
            CameraModel(
                name=cam.name,
                image_size=cam.image_size,
                intrinsics=cam.intrinsics,
                extrinsics=new_extrinsics,
            )
        )

    logger.info(
        f"Pinned camera '{cameras[camera_index].name}' to origin. "
        f"Adjusted {len(cameras)} camera extrinsics."
    )

    return result


# =============================================================================
# GROUND PLANE ALIGNMENT
# =============================================================================


def _triangulate_charuco_corners(
    *,
    cameras: list[CameraModel],
    all_observations: list[CharucoCornersObservation],
    board: CharucoBoardDefinition,
) -> NDArray[np.float64]:
    """Triangulate charuco corners into 3D for ground plane estimation.

    Uses DLT triangulation across all cameras for each frame, then stacks
    into (n_frames, n_corners, 3). Missing corners are filled with NaN.

    Returns:
        (n_frames, n_corners, 3) array of triangulated 3D positions.
    """
    # Group observations by frame
    cam_name_to_model = {cam.name: cam for cam in cameras}
    frame_groups: dict[int, dict[str, CharucoCornersObservation]] = {}
    for obs in all_observations:
        if obs.frame_index not in frame_groups:
            frame_groups[obs.frame_index] = {}
        frame_groups[obs.frame_index][obs.camera_name] = obs

    sorted_frames = sorted(frame_groups.keys())
    n_frames = len(sorted_frames)
    n_corners = board.n_corners

    result = np.full((n_frames, n_corners, 3), np.nan, dtype=np.float64)

    for fi, frame_idx in enumerate(sorted_frames):
        frame_obs = frame_groups[frame_idx]

        for corner_id in range(n_corners):
            # Collect 2D observations of this corner across cameras
            cam_observations: list[tuple[NDArray[np.float64], NDArray[np.float64]]] = []

            for cam_name, obs in frame_obs.items():
                cam = cam_name_to_model[cam_name]
                for c in obs.corners:
                    if c.corner_id == corner_id:
                        P = cam.projection_matrix
                        cam_observations.append((c.pixel_xy, P))
                        break

            if len(cam_observations) < 2:
                continue

            # DLT triangulation
            n_views = len(cam_observations)
            A = np.zeros((n_views * 2, 4), dtype=np.float64)
            for vi, (px, P) in enumerate(cam_observations):
                x, y = px
                A[vi * 2] = x * P[2] - P[0]
                A[vi * 2 + 1] = y * P[2] - P[1]

            _, _, vh = np.linalg.svd(A, full_matrices=False)
            pt_h = vh[-1]
            if abs(pt_h[3]) < 1e-10:
                continue
            result[fi, corner_id] = pt_h[:3] / pt_h[3]

    return result


def align_to_charuco_groundplane(
    *,
    cameras: list[CameraModel],
    board: CharucoBoardDefinition,
    all_observations: list[CharucoCornersObservation],
) -> list[CameraModel]:
    """Transform the world frame so the charuco board defines the ground plane.

    The charuco board's origin corner becomes the world origin, its X edge
    defines +X, and the board normal defines +Z (up).

    Args:
        cameras: Calibrated camera models.
        board: Board definition.
        all_observations: All frame observations for triangulation.

    Returns:
        Camera models with extrinsics adjusted to the new world frame.
    """
    logger.info("Aligning world frame to charuco ground plane...")

    # Triangulate all charuco corners
    charuco_3d = _triangulate_charuco_corners(
        cameras=cameras,
        all_observations=all_observations,
        board=board,
    )

    # Find a stationary frame
    still_frame_idx = find_still_charuco_frame(
        charuco_3d=charuco_3d,
        squares_x=board.squares_x,
        squares_y=board.squares_y,
    )
    logger.info(f"Using frame {still_frame_idx} for ground plane alignment")

    frame_corners = charuco_3d[still_frame_idx]

    # Validate key corners are visible
    origin = frame_corners[0]
    if np.isnan(origin).any():
        raise RuntimeError(
            "Origin charuco corner contains NaN in the selected frame. "
            "Cannot establish ground plane."
        )

    # Compute orthonormal basis from the board corners
    x_hat, y_hat, z_hat = compute_board_basis_vectors(
        charuco_frame=frame_corners,
        squares_x=board.squares_x,
        squares_y=board.squares_y,
    )

    # Rotation from charuco frame to current world frame
    R_charuco_to_world = np.column_stack([x_hat, y_hat, z_hat])

    # Transform all cameras: new extrinsics map from "charuco world" to camera
    result: list[CameraModel] = []
    for cam in cameras:
        R_cam = cam.extrinsics.rotation_matrix
        t_cam = cam.extrinsics.translation

        # Shift origin, then rotate
        t_delta = R_cam @ origin
        t_new = t_cam + t_delta

        # Compose with charuco-to-world rotation
        R_new = R_cam @ R_charuco_to_world

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

    logger.info("Ground plane alignment complete")
    return result
