"""Initialize camera intrinsics and extrinsics from charuco observations.

Intrinsics are initialized per-camera using cv2.calibrateCamera.
Extrinsics are initialized by:
  1. Estimating per-camera board poses via cv2.solvePnP
  2. Computing pairwise camera transforms from shared board observations
  3. Building a maximum spanning tree from shared observation counts
  4. Chaining transforms along the spanning tree to get all cameras in a common frame
"""

import logging
import queue
from collections import defaultdict

import cv2
import numpy as np
from numpy.typing import NDArray
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.cluster.vq import whiten
from scipy.linalg import inv as matrix_inverse
from scipy.spatial.transform import Rotation

from .models import (
    CameraExtrinsics,
    CameraIntrinsics,
    CharucoBoardDefinition,
    FrameObservation,
)

logger = logging.getLogger(__name__)


# =============================================================================
# INTRINSICS INITIALIZATION
# =============================================================================


def initialize_intrinsics(
    *,
    board: CharucoBoardDefinition,
    observations_by_camera: dict[str, list[FrameObservation]],
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
    observations: list[FrameObservation],
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

        rvec = rvec.ravel()
        tvec = tvec.ravel()
        R, _ = cv2.Rodrigues(rvec)

        M = np.eye(4, dtype=np.float64)
        M[:3, :3] = R
        M[:3, 3] = tvec
        poses[obs.frame_index] = M

    return poses


# =============================================================================
# PAIRWISE CAMERA TRANSFORMS
# =============================================================================


def _make_M(rvec: NDArray[np.float64], tvec: NDArray[np.float64]) -> NDArray[np.float64]:
    """Build a 4x4 transformation matrix from rvec + tvec."""
    R, _ = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64).ravel())
    M = np.eye(4, dtype=np.float64)
    M[:3, :3] = R
    M[:3, 3] = np.asarray(tvec, dtype=np.float64).ravel()
    return M


def _select_matrices_robust(matrices: list[NDArray[np.float64]]) -> list[NDArray[np.float64]]:
    """Cluster transformation matrices and return those from the largest cluster."""
    if len(matrices) <= 3:
        return matrices

    rvecs = []
    tvecs = []
    for M in matrices:
        rvec, _ = cv2.Rodrigues(M[:3, :3])
        rvecs.append(rvec.ravel())
        tvecs.append(M[:3, 3])

    features = np.hstack([np.array(rvecs), np.array(tvecs)])

    whitened = whiten(features)
    Z = linkage(whitened, method="ward")
    n_clust = max(len(matrices) // 10, 3)
    clusters = fcluster(Z, t=n_clust, criterion="maxclust")

    # Find largest cluster
    unique, counts = np.unique(clusters, return_counts=True)
    largest_cluster = unique[np.argmax(counts)]
    mask = clusters == largest_cluster

    return [matrices[i] for i in range(len(matrices)) if mask[i]]


def _mean_transform(matrices: list[NDArray[np.float64]]) -> NDArray[np.float64]:
    """Compute mean transformation matrix from a list of 4x4 transforms."""
    if len(matrices) == 0:
        raise ValueError("Cannot compute mean of empty matrix list")

    rvecs = []
    tvecs = []
    for M in matrices:
        rvec, _ = cv2.Rodrigues(M[:3, :3])
        rvecs.append(rvec.ravel())
        tvecs.append(M[:3, 3])

    mean_rvec = np.mean(rvecs, axis=0)
    mean_tvec = np.mean(tvecs, axis=0)

    if np.any(np.isnan(mean_rvec)) or np.any(np.isnan(mean_tvec)):
        raise ValueError("NaN in mean transform computation")

    return _make_M(mean_rvec, mean_tvec)


def _mean_transform_robust(
    matrices: list[NDArray[np.float64]],
    initial_estimate: NDArray[np.float64],
    error_threshold: float = 0.3,
    max_iterations: int = 5,
) -> NDArray[np.float64]:
    """Iteratively filter outlier transforms and recompute the mean."""
    current = initial_estimate

    for _ in range(max_iterations):
        kept = []
        for M in matrices:
            rot_diff = np.max(np.abs((M - current)[:3, :3]))
            if rot_diff < error_threshold:
                kept.append(M)

        if len(kept) == 0:
            # Fallback: keep best 50%
            errors = [np.max(np.abs((M - current)[:3, :3])) for M in matrices]
            sorted_idx = np.argsort(errors)
            n_keep = max(len(matrices) // 2, 3)
            kept = [matrices[i] for i in sorted_idx[:n_keep]]

        new_mean = _mean_transform(kept)
        diff = np.max(np.abs(new_mean - current))
        current = new_mean

        if diff < 0.001:
            break

    return current


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

    selected = _select_matrices_robust(transforms)
    initial = _mean_transform(selected)

    # Progressive refinement
    for threshold in [0.5, 0.3, 0.15, 0.1]:
        refined = _mean_transform_robust(
            matrices=transforms,
            initial_estimate=initial,
            error_threshold=threshold,
        )
        diff = np.max(np.abs(refined - initial))
        if diff > 10.0:
            break
        initial = refined

    return initial


# =============================================================================
# SPANNING TREE + EXTRINSICS
# =============================================================================


def _build_camera_graph(
    *,
    camera_names: list[str],
    all_board_poses: dict[str, dict[int, NDArray[np.float64]]],
) -> dict[int, list[int]]:
    """Build a maximum spanning tree from shared observation counts.

    Returns an adjacency list graph (indices into camera_names).
    """
    n_cams = len(camera_names)

    # Count shared frames for each camera pair
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

    # Kruskal-like MST construction (greedy, maximum weight)
    components = {i: i for i in range(n_cams)}
    edges = set(connections.items())
    graph: dict[int, list[int]] = defaultdict(list)

    for _ in range(n_cams - 1):
        if len(edges) == 0:
            # Check which cameras are disconnected
            comp_map = {camera_names[k]: v for k, v in components.items()}
            raise ValueError(
                f"Cannot build connected calibration graph. "
                f"Some cameras have no shared board observations. "
                f"Component map: {comp_map}"
            )

        (a, b), weight = max(edges, key=lambda x: x[1])
        graph[a].append(b)
        graph[b].append(a)

        # Merge components
        match_comp = components[a]
        replace_comp = components[b]
        for k in components:
            if components[k] == match_comp:
                components[k] = replace_comp

        # Remove edges within same component
        for e in list(edges):
            (ea, eb), _ = e
            if components[ea] == components[eb]:
                edges.discard(e)

    return dict(graph)


def _find_spanning_tree_pairs(
    graph: dict[int, list[int]],
    root: int = 0,
) -> list[tuple[int, int]]:
    """BFS from root to produce (parent, child) pairs for the spanning tree."""
    pairs: list[tuple[int, int]] = []
    visited: set[int] = set()
    q: queue.Queue[int] = queue.Queue()
    q.put(root)
    visited.add(root)

    while not q.empty():
        node = q.get()
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                q.put(neighbor)
                pairs.append((node, neighbor))

    return pairs


def initialize_extrinsics(
    *,
    board: CharucoBoardDefinition,
    observations_by_camera: dict[str, list[FrameObservation]],
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
    graph = _build_camera_graph(
        camera_names=camera_names,
        all_board_poses=all_board_poses,
    )
    pairs = _find_spanning_tree_pairs(graph=graph, root=0)
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
        rvec, _ = cv2.Rodrigues(M[:3, :3])
        tvec = M[:3, 3]

        results[cam_name] = CameraExtrinsics.from_rodrigues(
            rvec=rvec.ravel(),
            tvec=tvec,
        )
        logger.info(
            f"Camera '{cam_name}': "
            f"translation_norm={np.linalg.norm(tvec):.1f}mm, "
            f"rotation_angle={np.linalg.norm(rvec.ravel()) * 180 / np.pi:.1f}°"
        )

    return results


# =============================================================================
# BOARD POSE INITIALIZATION (for solver)
# =============================================================================


def initialize_board_poses(
    *,
    board: CharucoBoardDefinition,
    observations_by_camera: dict[str, list[FrameObservation]],
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
    frame_lookup: dict[int, list[tuple[str, FrameObservation]]] = defaultdict(list)
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

            # Board pose in camera frame: T_cam_board
            rvec = rvec.ravel()
            tvec = tvec.ravel()
            R_cam_board, _ = cv2.Rodrigues(rvec)
            T_cam_board = np.eye(4, dtype=np.float64)
            T_cam_board[:3, :3] = R_cam_board
            T_cam_board[:3, 3] = tvec

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
