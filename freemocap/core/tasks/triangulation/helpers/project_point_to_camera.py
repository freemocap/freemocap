import numpy as np
from numpy._typing import NDArray


def project_point_to_camera(
    *,
    point_3d: NDArray[np.float64],
    extrinsics_mat: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Project a single 3D world point through a [R|t] matrix.

    Args:
        point_3d: shape (3,) - 3D point [X, Y, Z] in world coordinates.
        extrinsics_mat: shape (3, 4) - [R|t] matrix.

    Returns:
        shape (2,) - normalized image coordinates [u, v] before applying intrinsics.
    """
    hom = np.array([point_3d[0], point_3d[1], point_3d[2], 1.0], dtype=np.float64)
    projected = extrinsics_mat @ hom
    return projected[:2] / projected[2]
