"""Shared ground-plane alignment math for camera calibration.

Contains format-agnostic functions for computing the charuco board's
coordinate frame from triangulated 3D corners and finding a frame
where the board is stationary.

Used by both the anipose and pyceres calibration paths.
"""

import numpy as np
from numpy.typing import NDArray


class CharucoVisibilityError(RuntimeError):
    """Raised when no frame satisfies the 'all-corners-visible & stationary' criteria."""


class CharucoVelocityError(RuntimeError):
    """Raised when the velocity of the ChArUco corners is too high to be considered stationary."""


def get_charuco_key_corner_indices(
    squares_x: int,
    squares_y: int,
) -> tuple[int, int]:
    """Get the corner indices that define the board's X and Y axes.

    For a board with ``squares_x`` columns and ``squares_y`` rows, the internal
    corners form a grid of ``(squares_x-1) x (squares_y-1)``.  Corner 0 is the
    origin, the returned ``idx_x`` is at the far end of the X axis, and ``idx_y``
    is at the far end of the Y axis.

    Args:
        squares_x: Number of squares in the X (width) direction.
        squares_y: Number of squares in the Y (height) direction.

    Returns:
        Tuple of (idx_x, idx_y) corner indices.
    """
    num_cols = squares_x - 1
    num_rows = squares_y - 1
    idx_y = num_cols * (num_rows - 1)
    idx_x = num_cols - 1
    return idx_x, idx_y


def compute_board_basis_vectors(
    charuco_frame: NDArray[np.float64],
    squares_x: int,
    squares_y: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Compute orthonormal basis vectors of the charuco board's coordinate frame.

    X axis: from corner 0 toward ``idx_x`` (board "right").
    Z axis: board normal, out of the *printed* face (physical "up" when the
        board lies printed-side-up on the floor).

    OpenCV's CharucoBoard object points use image-plane conventions: +X is
    board-right and +Y is board-*down* (matching how marker IDs are laid out
    in the generated image). With that handedness, ``cross(x_hat, y_raw)``
    points into the *back* of the printed face. We swap the operand order so
    +Z comes out of the front, and re-derive y_hat from the flipped z to
    keep the basis right-handed.

    Args:
        charuco_frame: (n_corners, 3) array of 3D corner positions for one frame.
        squares_x: Number of squares in the X direction.
        squares_y: Number of squares in the Y direction.

    Returns:
        Tuple of (x_hat, y_hat, z_hat) unit vectors.
    """
    origin = charuco_frame[0]
    idx_x, idx_y = get_charuco_key_corner_indices(squares_x=squares_x, squares_y=squares_y)

    x_vec = charuco_frame[idx_x] - origin
    y_vec = charuco_frame[idx_y] - origin

    x_hat = x_vec / np.linalg.norm(x_vec)
    y_hat_raw = y_vec / np.linalg.norm(y_vec)
    z_hat = np.cross(y_hat_raw, x_hat)
    z_hat = z_hat / np.linalg.norm(z_hat)
    y_hat = np.cross(z_hat, x_hat)
    y_hat = y_hat / np.linalg.norm(y_hat)

    return x_hat, y_hat, z_hat


def find_still_charuco_frame(
    charuco_3d: NDArray[np.float64],
    squares_x: int,
    squares_y: int,
    search_start: int = 0,
    search_range: int = 120,
) -> int:
    """Find the frame where the charuco board is most stationary.

    Examines the origin, X-axis-end, and Y-axis-end corners. Picks the frame
    (within the search range) where the maximum corner velocity is minimized.

    Args:
        charuco_3d: (n_frames, n_corners, 3) triangulated 3D corner positions.
        squares_x: Board squares in X.
        squares_y: Board squares in Y.
        search_start: Frame index to start searching from.
        search_range: Number of frames to search.

    Returns:
        Frame index (into ``charuco_3d``) of the stillest frame.

    Raises:
        CharucoVisibilityError: No frame has all three key corners visible.
        CharucoVelocityError: All visible frames have velocity above threshold.
    """
    n_frames = charuco_3d.shape[0]
    idx_x, idx_y = get_charuco_key_corner_indices(squares_x=squares_x, squares_y=squares_y)
    key_indices = [0, idx_y, idx_x]

    # Compute search slice
    start = max(0, search_start)
    end = min(n_frames, start + search_range)
    if end <= start:
        raise CharucoVisibilityError("Search range is empty — not enough frames.")

    key_corners = charuco_3d[start:end, key_indices, :]  # (range, 3_corners, 3_xyz)
    velocity = np.linalg.norm(np.diff(key_corners, axis=0), axis=2)  # (range-1, 3_corners)

    visible = ~np.isnan(velocity).any(axis=1)
    if not visible.any():
        raise CharucoVisibilityError(
            "No frame found where all three key ChArUco corners are visible and have valid velocity."
        )

    max_velocity_per_frame = np.nanmax(velocity[visible], axis=1)

    MAX_ALLOWED_VELOCITY = 1.0
    if np.nanmin(max_velocity_per_frame) > MAX_ALLOWED_VELOCITY:
        raise CharucoVelocityError(
            f"All frames have ChArUco corner velocity > {MAX_ALLOWED_VELOCITY:.2f} — "
            f"check that the board is stationary."
        )

    best_visible_idx = int(np.nanargmin(max_velocity_per_frame))
    # +1 because np.diff shifts indices by 1
    best_frame_idx = np.where(visible)[0][best_visible_idx] + 1 + start

    return int(best_frame_idx)
