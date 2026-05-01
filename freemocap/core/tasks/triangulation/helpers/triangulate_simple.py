import numpy as np
from numpy._typing import NDArray


def triangulate_simple(
    *,
    points: NDArray[np.float64],
    extrinsics_mats: NDArray[np.float64],
) -> NDArray[np.float64]:
    """DLT triangulation of a single 3D point from N cameras via SVD.

    Args:
        points: shape (N, 2) - undistorted-normalized 2D observations.
        extrinsics_mats: shape (N, 3, 4) - [R|t] matrices.

    Returns:
        shape (3,) - 3D point in world coordinates.
    """
    num_cams = len(extrinsics_mats)
    a_matrix = np.zeros((num_cams * 2, 4), dtype=np.float64)
    for i in range(num_cams):
        x, y = points[i]
        mat = extrinsics_mats[i]
        a_matrix[(i * 2): (i * 2 + 1)] = x * mat[2] - mat[0]
        a_matrix[(i * 2 + 1): (i * 2 + 2)] = y * mat[2] - mat[1]
    _, _, vh = np.linalg.svd(a_matrix, full_matrices=True)
    p_homogeneous = vh[-1]
    return p_homogeneous[:3] / p_homogeneous[3]


def triangulate_simple_batch(
    *,
    points_batch: NDArray[np.float64],
    extrinsics_mats: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Batched DLT triangulation of P 3D points from N cameras, single SVD call.

    All P points must have valid (non-NaN) observations from ALL N cameras.

    Args:
        points_batch: shape (P, N, 2) - undistorted-normalized 2D observations.
        extrinsics_mats: shape (N, 3, 4) - [R|t] matrices.

    Returns:
        shape (P, 3) - 3D points in world coordinates.
    """
    n_points, n_cameras, _ = points_batch.shape

    x = points_batch[:, :, 0]  # (P, N)
    y = points_batch[:, :, 1]  # (P, N)

    # rows_x[p, c] = x[p,c] * ext[c,2] - ext[c,0]  shape (P, N, 4)
    rows_x = x[:, :, None] * extrinsics_mats[None, :, 2, :] - extrinsics_mats[None, :, 0, :]
    rows_y = y[:, :, None] * extrinsics_mats[None, :, 2, :] - extrinsics_mats[None, :, 1, :]

    # Interleave into DLT A-matrix: shape (P, 2*N, 4)
    A = np.empty((n_points, 2 * n_cameras, 4), dtype=np.float64)
    A[:, 0::2, :] = rows_x
    A[:, 1::2, :] = rows_y

    _, _, Vh = np.linalg.svd(A, full_matrices=False)  # Vh: (P, 4, 4)
    p_hom = Vh[:, -1, :]  # (P, 4)
    return p_hom[:, :3] / p_hom[:, 3:4]  # (P, 3)
