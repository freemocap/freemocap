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
