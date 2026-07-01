"""Shared ground-plane alignment math for camera calibration.

Format-agnostic functions for estimating the charuco board's ground-plane pose
from triangulated 3D corners: finding a stable window where the board is still,
taking per-corner medians across it, and fitting the known board model with Kabsch.

Used by both the anipose and pyceres calibration paths.
"""

import numpy as np
from numpy.typing import NDArray


class CharucoVisibilityError(RuntimeError):
    """Raised when too few charuco corners are observed in the stable window to estimate the board."""


class CharucoStabilityError(RuntimeError):
    """Raised when no contiguous run of frames is stable enough to define the ground plane."""


class CharucoGeometryError(RuntimeError):
    """Raised when the stable charuco corners are too few or collinear to define a board frame."""


def find_stable_window(
    charuco_3d: NDArray[np.float64],
    *,
    velocity_threshold: float = 2.0,
    min_visible_corners_per_frame: int = 3,
    min_run_frames: int = 10,
) -> tuple[int, int]:
    """Find the longest contiguous run of frames over which the board is still.

    Motion for a transition t -> t+1 is the MEDIAN per-corner displacement over the
    corners visible in BOTH frames — robust to a changing/blinky visibility set,
    unlike a centroid velocity.

    Args:
        charuco_3d: (n_frames, n_corners, 3) triangulated corners, NaN where unseen.
        velocity_threshold: mm/frame below which a transition counts as still.
        min_visible_corners_per_frame: a transition is only scored if at least this
            many corners are visible in both of its frames.
        min_run_frames: the chosen run must be at least this many frames long.

    Returns:
        (start, end) half-open frame indices of the chosen stable run.

    Raises:
        CharucoStabilityError: if no run meets the threshold and minimum length.
    """
    n_frames = int(charuco_3d.shape[0])
    if n_frames < 2:
        raise CharucoStabilityError(
            f"Need at least 2 frames to assess stability, got {n_frames}."
        )

    finite = np.isfinite(charuco_3d).all(axis=2)  # (n_frames, n_corners)

    motion = np.full(n_frames - 1, np.inf, dtype=np.float64)
    for t in range(n_frames - 1):
        common = finite[t] & finite[t + 1]
        if int(common.sum()) >= min_visible_corners_per_frame:
            displacement = np.linalg.norm(
                charuco_3d[t + 1, common] - charuco_3d[t, common], axis=1
            )
            motion[t] = float(np.median(displacement))

    stable = motion < velocity_threshold

    runs: list[tuple[int, int, float]] = []  # (frame_start, frame_end_exclusive, mean_motion)
    t = 0
    while t < stable.shape[0]:
        if not stable[t]:
            t += 1
            continue
        run_start = t
        while t < stable.shape[0] and stable[t]:
            t += 1
        runs.append((run_start, t + 1, float(np.mean(motion[run_start:t]))))

    if not runs:
        raise CharucoStabilityError(
            f"No contiguous run of frames stayed below {velocity_threshold} mm/frame — "
            f"check that the board is held still."
        )

    # Longest run wins; ties broken by lowest mean motion.
    frame_start, frame_end, _ = min(runs, key=lambda run: (-(run[1] - run[0]), run[2]))

    if frame_end - frame_start < min_run_frames:
        raise CharucoStabilityError(
            f"Longest stable run is {frame_end - frame_start} frames, "
            f"need >= {min_run_frames}."
        )

    return frame_start, frame_end


def aggregate_median_corners(
    charuco_3d: NDArray[np.float64],
    window: tuple[int, int],
    *,
    min_observations_per_corner: int = 3,
) -> tuple[NDArray[np.int_], NDArray[np.float64]]:
    """Per-corner median 3D position over a frame window, ignoring NaN (blinky) gaps.

    Args:
        charuco_3d: (n_frames, n_corners, 3) triangulated corners, NaN where unseen.
        window: (start, end) half-open frame range to aggregate over.
        min_observations_per_corner: a corner joins the result only if it has at
            least this many finite samples in the window (discards 1-2 frame blips).

    Returns:
        (valid_ids (K,), median_points (K, 3)) for the well-observed corners.

    Raises:
        CharucoVisibilityError: if no corner reaches the observation threshold.
    """
    start, end = window
    window_data = charuco_3d[start:end]  # (W, n_corners, 3)
    finite = np.isfinite(window_data).all(axis=2)  # (W, n_corners)
    observation_count = finite.sum(axis=0)  # (n_corners,)

    valid_ids = np.where(observation_count >= min_observations_per_corner)[0]
    if valid_ids.size == 0:
        raise CharucoVisibilityError(
            f"No charuco corner was observed >= {min_observations_per_corner} times "
            f"in the stable window [{start}, {end})."
        )

    median_points = np.nanmedian(window_data[:, valid_ids, :], axis=0)  # (K, 3)
    return valid_ids, median_points


def fit_board_pose_kabsch(
    board_points: NDArray[np.float64],
    measured_points: NDArray[np.float64],
    *,
    collinearity_eps: float = 1e-6,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Best-fit rigid transform mapping board-frame corners to measured world corners.

    Solves the orthogonal Procrustes / Kabsch problem with known correspondences
    (corner i of ``board_points`` matches corner i of ``measured_points``).

    Args:
        board_points: (K, 3) known board-frame corner coordinates (z = 0).
        measured_points: (K, 3) corresponding measured world coordinates.
        collinearity_eps: relative floor on the 2nd singular value of the board
            points; below it the corners are treated as collinear.

    Returns:
        (rotation, translation) such that ``world = rotation @ board + translation``.
        The board axes in world are the columns of ``rotation``; the board origin in
        world is ``translation``.

    Raises:
        CharucoGeometryError: fewer than 3 corners, or the corners are collinear.
    """
    board_points = np.asarray(board_points, dtype=np.float64)
    measured_points = np.asarray(measured_points, dtype=np.float64)
    if (
        board_points.shape != measured_points.shape
        or board_points.ndim != 2
        or board_points.shape[1] != 3
    ):
        raise ValueError(
            f"board_points and measured_points must be equal-shaped (K, 3); "
            f"got {board_points.shape} and {measured_points.shape}."
        )

    n_points = board_points.shape[0]
    if n_points < 3:
        raise CharucoGeometryError(
            f"Need >= 3 corners to define a board frame, got {n_points}."
        )

    board_centroid = board_points.mean(axis=0)
    measured_centroid = measured_points.mean(axis=0)
    board_centered = board_points - board_centroid
    measured_centered = measured_points - measured_centroid

    # Collinearity test on the noise-free board coordinates: a line has 2nd sv ~ 0.
    board_singular_values = np.linalg.svd(board_centered, compute_uv=False)
    if board_singular_values[1] <= collinearity_eps * board_singular_values[0]:
        raise CharucoGeometryError(
            "The observed charuco corners are collinear; cannot define a 2D board frame."
        )

    cross_covariance = board_centered.T @ measured_centered
    u, _, vt = np.linalg.svd(cross_covariance)
    reflection = np.sign(np.linalg.det(vt.T @ u.T))
    rotation = vt.T @ np.diag([1.0, 1.0, reflection]) @ u.T
    translation = measured_centroid - rotation @ board_centroid
    return rotation, translation


def orient_up_toward_cameras(
    rotation_matrix: NDArray[np.float64],
    origin: NDArray[np.float64],
    camera_centers: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Ensure the board's +Z axis points toward the cameras (physical "up").

    Kabsch fixes the board normal only up to sign — coplanar points cannot tell which
    face is up. Cameras in a mocap rig sit above the floor, so +Z should have a
    positive component toward the camera centroid. If it does not, flip Z and
    re-derive Y to keep the basis right-handed (X is preserved).

    Args:
        rotation_matrix: (3, 3) board-to-world rotation, columns [x | y | z].
        origin: (3,) board origin in world.
        camera_centers: (n_cameras, 3) camera centers in world.

    Returns:
        (3, 3) rotation matrix with corrected, right-handed [x | y | z] columns.
    """
    rotation_matrix = np.asarray(rotation_matrix, dtype=np.float64)
    origin = np.asarray(origin, dtype=np.float64)
    camera_centroid = np.asarray(camera_centers, dtype=np.float64).mean(axis=0)

    x_hat = rotation_matrix[:, 0]
    z_hat = rotation_matrix[:, 2]

    if np.dot(z_hat, camera_centroid - origin) < 0:
        z_hat = -z_hat
        y_hat = np.cross(z_hat, x_hat)
        return np.column_stack([x_hat, y_hat, z_hat])

    return rotation_matrix.copy()


def estimate_board_groundplane(
    charuco_3d: NDArray[np.float64],
    *,
    board_points: NDArray[np.float64],
    camera_centers: NDArray[np.float64],
    velocity_threshold: float = 2.0,
    min_visible_corners_per_frame: int = 3,
    min_run_frames: int = 10,
    min_observations_per_corner: int = 3,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Estimate the board ground-plane pose robustly from triangulated corners.

    Pipeline: stable window -> per-corner median -> Kabsch fit to the known board
    model -> orient +Z toward the cameras.

    Args:
        charuco_3d: (n_frames, n_corners, 3) triangulated corners, NaN where unseen.
        board_points: (n_corners, 3) known board-frame corner coordinates.
        camera_centers: (n_cameras, 3) camera centers in world coordinates.

    Returns:
        (rotation_matrix, origin): board-to-world rotation (columns = x/y/z axes)
        and the board origin in world.

    Raises:
        CharucoStabilityError, CharucoVisibilityError, CharucoGeometryError.
    """
    board_points = np.asarray(board_points, dtype=np.float64)

    window = find_stable_window(
        charuco_3d,
        velocity_threshold=velocity_threshold,
        min_visible_corners_per_frame=min_visible_corners_per_frame,
        min_run_frames=min_run_frames,
    )
    valid_ids, median_points = aggregate_median_corners(
        charuco_3d, window, min_observations_per_corner=min_observations_per_corner
    )
    rotation, origin = fit_board_pose_kabsch(board_points[valid_ids], median_points)
    rotation = orient_up_toward_cameras(rotation, origin, camera_centers)
    return rotation, origin
