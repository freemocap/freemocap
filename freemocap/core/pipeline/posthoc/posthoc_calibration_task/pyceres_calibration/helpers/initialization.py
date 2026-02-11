"""Initialize camera intrinsics and extrinsics from charuco observations.

Intrinsics are initialized per-camera using cv2.calibrateCamera.
Extrinsics are initialized by:
  1. Estimating per-camera board poses via cv2.solvePnP
  2. Computing pairwise camera transforms from shared board observations
  3. Building a maximum spanning tree from shared observation counts
  4. Chaining transforms along the spanning tree to get all cameras in a common frame
"""

import logging
from collections import defaultdict

import cv2
import numpy as np
from numpy.typing import NDArray
from scipy.linalg import inv as matrix_inverse
from scipy.spatial.transform import Rotation

from freemocap.core.pipeline.posthoc.posthoc_calibration_task.shared.transform_math import (
    build_maximum_spanning_tree,
    find_spanning_tree_pairs,
    get_rtvec,
    make_M,
    robust_average_transforms,
)
from .models import (
    CameraExtrinsics,
    CameraIntrinsics,
    CharucoBoardDefinition,
    CharucoCornersObservation,
)

logger = logging.getLogger(__name__)


# =============================================================================
# INTRINSICS INITIALIZATION
# =============================================================================


def initialize_intrinsics(
    *,
    board: CharucoBoardDefinition,
    observations_by_camera: dict[str, list[CharucoCornersObservation]],
    image_sizes: dict[str, tuple[int, int]],
    min_corners: int = 7,
) -> dict[str, CameraIntrinsics]:
    """Initialize camera intrinsics using cv2.calibrateCamera.

    Args:
        board: Charuco board definition with known 3D corner positions.
        observations_by_camera: Per-camera list of frame observations.
        image_sizes: Per-camera image size as (width, height).
        min_corners: Minimum corners in a frame for it to be used.

    Returns:
        Per-camera CameraIntrinsics models.
    """
    board_corners_3d = board.corner_positions_board_frame
    results: dict[str, CameraIntrinsics] = {}

    for cam_name, observations in observations_by_camera.items():
        if cam_name not in image_sizes:
            raise KeyError(f"No image size for camera '{cam_name}'")

        width, height = image_sizes[cam_name]
        obj_points: list[NDArray[np.float64]] = []
        img_points: list[NDArray[np.float64]] = []

        for obs in observations:
            if obs.n_corners < min_corners:
                continue

            obj_pts = np.array(
                [board_corners_3d[c.corner_id] for c in obs.corners],
                dtype=np.float32,
            )
            img_pts = np.array(
                [c.pixel_xy for c in obs.corners],
                dtype=np.float32,
            ).reshape(-1, 1, 2)

            obj_points.append(obj_pts)
            img_points.append(img_pts)

        if len(obj_points) == 0:
            raise ValueError(
                f"Camera '{cam_name}': no frames with >= {min_corners} corners. "
                f"Had {len(observations)} total frames."
            )

        logger.info(f"Camera '{cam_name}': calibrating intrinsics from {len(obj_points)} frames")

        ret, camera_matrix, dist_coeffs, _, _ = cv2.calibrateCamera(
            obj_points,
            img_points,
            imageSize=(width, height),
            cameraMatrix=None,
            distCoeffs=None,
            flags=cv2.CALIB_FIX_K3 | cv2.CALIB_FIX_K4 | cv2.CALIB_FIX_K5 | cv2.CALIB_FIX_K6,
        )

        if not ret:
            raise RuntimeError(f"Camera '{cam_name}': cv2.calibrateCamera failed")

        dist = dist_coeffs.ravel()
        results[cam_name] = CameraIntrinsics(
            fx=float(camera_matrix[0, 0]),
            fy=float(camera_matrix[1, 1]),
            cx=float(camera_matrix[0, 2]),
            cy=float(camera_matrix[1, 2]),
            k1=float(dist[0]) if len(dist) > 0 else 0.0,
            k2=float(dist[1]) if len(dist) > 1 else 0.0,
            p1=float(dist[2]) if len(dist) > 2 else 0.0,
            p2=float(dist[3]) if len(dist) > 3 else 0.0,
        )

        logger.info(
            f"Camera '{cam_name}': fx={results[cam_name].fx:.1f}, "
            f"fy={results[cam_name].fy:.1f}, "
            f"cx={results[cam_name].cx:.1f}, cy={results[cam_name].cy:.1f}, "
            f"k1={results[cam_name].k1:.4f}, k2={results[cam_name].k2:.4f}"
        )

    return results


# =============================================================================
# BOARD POSE ESTIMATION
# =============================================================================


def _estimate_board_poses(
    *,
    board: CharucoBoardDefinition,
    observations: list[CharucoCornersObservation],
    intrinsics: CameraIntrinsics,
    min_corners: int = 6,
) -> dict[int, NDArray[np.float64]]:
    """Estimate board pose (4x4 transform) per frame for a single camera.

    Args:
        board: Board definition.
        observations: Frame observations for one camera.
        intrinsics: Camera intrinsics for this camera.
        min_corners: Minimum corners needed for solvePnP.

    Returns:
        Dict mapping frame_index → 4x4 transformation matrix (board-to-camera).
    """
    board_corners_3d = board.corner_positions_board_frame
    K = intrinsics.to_camera_matrix()
    D = intrinsics.to_dist_coeffs()

    poses: dict[int, NDArray[np.float64]] = {}

    for obs in observations:
        if obs.n_corners < min_corners:
            continue

        obj_pts = np.array(
            [board_corners_3d[c.corner_id] for c in obs.corners],
            dtype=np.float64,
        )
        img_pts = np.array(
            [c.pixel_xy for c in obs.corners],
            dtype=np.float64,
        ).reshape(-1, 1, 2)

        success, rvec, tvec = cv2.solvePnP(
            objectPoints=obj_pts,
            imagePoints=img_pts,
            cameraMatrix=K,
            distCoeffs=D,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not success:
            continue

        poses[obs.frame_index] = make_M(rvec=rvec.ravel(), tvec=tvec.ravel())

    return poses


# =============================================================================
# PAIRWISE CAMERA TRANSFORMS
# =============================================================================


def _compute_pairwise_transform(
    *,
    poses_a: dict[int, NDArray[np.float64]],
    poses_b: dict[int, NDArray[np.float64]],
) -> NDArray[np.float64]:
    """Compute the rigid transform from camera B's frame to camera A's frame.

    For each shared frame: T_A_board @ inv(T_B_board) gives T_A_B.
    Robustly averages across all shared frames.
    """
    shared_frames = set(poses_a.keys()) & set(poses_b.keys())
    if len(shared_frames) == 0:
        raise ValueError("No shared frames between camera pair")

    transforms: list[NDArray[np.float64]] = []
    for frame_idx in sorted(shared_frames):
        M_a = poses_a[frame_idx]
        M_b = poses_b[frame_idx]
        T_a_b = M_a @ matrix_inverse(M_b)
        transforms.append(T_a_b)

    logger.debug(f"  {len(transforms)} shared frames for pairwise transform")

    return robust_average_transforms(transforms)


# =============================================================================
# EXTRINSICS INITIALIZATION
# =============================================================================


def initialize_extrinsics(
    *,
    board: CharucoBoardDefinition,
    observations_by_camera: dict[str, list[CharucoCornersObservation]],
    intrinsics: dict[str, CameraIntrinsics],
    camera_names: list[str],
) -> dict[str, CameraExtrinsics]:
    """Initialize camera extrinsics by chaining pairwise transforms along a spanning tree.

    Camera 0 is placed at the world origin (identity transform). All other cameras
    are expressed relative to it via a maximum-weight spanning tree of shared
    board observations.

    Args:
        board: Board definition.
        observations_by_camera: Per-camera frame observations.
        intrinsics: Per-camera intrinsics (already initialized).
        camera_names: Ordered camera names. Camera 0 becomes the origin.

    Returns:
        Per-camera CameraExtrinsics models.
    """
    n_cams = len(camera_names)
    logger.info(f"Initializing extrinsics for {n_cams} cameras")

    # Step 1: Estimate board poses per camera per frame
    all_board_poses: dict[str, dict[int, NDArray[np.float64]]] = {}
    for cam_name in camera_names:
        if cam_name not in observations_by_camera:
            raise KeyError(f"No observations for camera '{cam_name}'")
        if cam_name not in intrinsics:
            raise KeyError(f"No intrinsics for camera '{cam_name}'")

        poses = _estimate_board_poses(
            board=board,
            observations=observations_by_camera[cam_name],
            intrinsics=intrinsics[cam_name],
        )
        all_board_poses[cam_name] = poses
        logger.info(f"Camera '{cam_name}': estimated board pose in {len(poses)} frames")

    # Step 2: Build spanning tree from shared observation counts
    connections: dict[tuple[int, int], int] = {}
    for i in range(n_cams):
        frames_i = set(all_board_poses[camera_names[i]].keys())
        for j in range(i + 1, n_cams):
            frames_j = set(all_board_poses[camera_names[j]].keys())
            shared = len(frames_i & frames_j)
            if shared > 0:
                connections[(i, j)] = shared
                connections[(j, i)] = shared

    if len(connections) == 0:
        raise ValueError(
            "No shared observations between any camera pair. "
            "Ensure cameras have overlapping views of the charuco board."
        )

    graph = build_maximum_spanning_tree(
        connection_counts=connections,
        n_nodes=n_cams,
        node_labels=camera_names,
    )
    pairs = find_spanning_tree_pairs(graph=graph, root=0)
    logger.info(f"Spanning tree pairs: {[(camera_names[a], camera_names[b]) for a, b in pairs]}")

    # Step 3: Chain pairwise transforms from root
    cam_to_world: dict[int, NDArray[np.float64]] = {0: np.eye(4, dtype=np.float64)}

    for parent_idx, child_idx in pairs:
        parent_name = camera_names[parent_idx]
        child_name = camera_names[child_idx]

        logger.info(f"Computing transform: {child_name} → {parent_name}")

        pairwise = _compute_pairwise_transform(
            poses_a=all_board_poses[child_name],
            poses_b=all_board_poses[parent_name],
        )
        cam_to_world[child_idx] = pairwise @ cam_to_world[parent_idx]

    # Step 4: Convert 4x4 matrices to CameraExtrinsics
    results: dict[str, CameraExtrinsics] = {}
    for cam_idx, cam_name in enumerate(camera_names):
        if cam_idx not in cam_to_world:
            raise RuntimeError(
                f"Camera '{cam_name}' (index {cam_idx}) not reached by spanning tree. "
                f"This indicates a bug in graph construction."
            )

        M = cam_to_world[cam_idx]
        rvec, tvec = get_rtvec(M)

        results[cam_name] = CameraExtrinsics.from_rodrigues(
            rvec=rvec,
            tvec=tvec,
        )
        logger.info(
            f"Camera '{cam_name}': "
            f"translation_norm={np.linalg.norm(tvec):.1f}mm, "
            f"rotation_angle={np.linalg.norm(rvec) * 180 / np.pi:.1f}°"
        )

    return results


# =============================================================================
# BOARD POSE INITIALIZATION (for solver)
# =============================================================================


def initialize_board_poses(
    *,
    board: CharucoBoardDefinition,
    observations_by_camera: dict[str, list[CharucoCornersObservation]],
    intrinsics: dict[str, CameraIntrinsics],
    extrinsics: dict[str, CameraExtrinsics],
    all_frame_indices: list[int],
) -> dict[int, tuple[NDArray[np.float64], NDArray[np.float64]]]:
    """Initialize board poses in world frame for each frame.

    Uses the first camera with a valid solvePnP result to estimate the board
    pose in that camera's frame, then transforms it to the world frame.

    Args:
        board: Board definition.
        observations_by_camera: Per-camera frame observations.
        intrinsics: Per-camera intrinsics.
        extrinsics: Per-camera extrinsics.
        all_frame_indices: Sorted list of all frame indices to initialize.

    Returns:
        Dict mapping frame_index → (quaternion_wxyz, translation) in world frame.
    """
    board_corners_3d = board.corner_positions_board_frame
    board_poses: dict[int, tuple[NDArray[np.float64], NDArray[np.float64]]] = {}

    # Build per-frame lookup: frame_index → list of (cam_name, observation)
    frame_lookup: dict[int, list[tuple[str, CharucoCornersObservation]]] = defaultdict(list)
    for cam_name, observations in observations_by_camera.items():
        for obs in observations:
            frame_lookup[obs.frame_index].append((cam_name, obs))

    for frame_idx in all_frame_indices:
        if frame_idx not in frame_lookup:
            # No observations in this frame — use identity as fallback
            board_poses[frame_idx] = (
                np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64),
                np.zeros(3, dtype=np.float64),
            )
            continue

        # Try each camera until we get a valid PnP result
        found = False
        for cam_name, obs in frame_lookup[frame_idx]:
            if obs.n_corners < 6:
                continue

            K = intrinsics[cam_name].to_camera_matrix()
            D = intrinsics[cam_name].to_dist_coeffs()

            obj_pts = np.array(
                [board_corners_3d[c.corner_id] for c in obs.corners],
                dtype=np.float64,
            )
            img_pts = np.array(
                [c.pixel_xy for c in obs.corners],
                dtype=np.float64,
            ).reshape(-1, 1, 2)

            success, rvec, tvec = cv2.solvePnP(
                objectPoints=obj_pts,
                imagePoints=img_pts,
                cameraMatrix=K,
                distCoeffs=D,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )

            if not success:
                continue

            # Board pose in camera frame
            T_cam_board = make_M(rvec=rvec.ravel(), tvec=tvec.ravel())

            # Camera extrinsics: T_cam_world (world → camera)
            ext = extrinsics[cam_name]
            R_cam_world = ext.rotation_matrix
            t_cam_world = ext.translation
            T_cam_world = np.eye(4, dtype=np.float64)
            T_cam_world[:3, :3] = R_cam_world
            T_cam_world[:3, 3] = t_cam_world

            # Board in world frame: T_world_board = inv(T_cam_world) @ T_cam_board
            T_world_board = matrix_inverse(T_cam_world) @ T_cam_board

            # Extract quaternion (wxyz) and translation
            R_world_board = T_world_board[:3, :3]
            t_world_board = T_world_board[:3, 3]
            quat_xyzw = Rotation.from_matrix(R_world_board).as_quat()
            quat_wxyz = np.array(
                [quat_xyzw[3], quat_xyzw[0], quat_xyzw[1], quat_xyzw[2]],
                dtype=np.float64,
            )

            board_poses[frame_idx] = (quat_wxyz, t_world_board)
            found = True
            break

        if not found:
            board_poses[frame_idx] = (
                np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64),
                np.zeros(3, dtype=np.float64),
            )

    logger.info(
        f"Initialized board poses for {len(board_poses)} frames "
        f"({sum(1 for q, _ in board_poses.values() if not np.allclose(q, [1, 0, 0, 0]))} with valid PnP)"
    )

    return board_poses
