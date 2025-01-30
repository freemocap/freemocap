import numpy as np
from numba import jit


@jit(nopython=True, parallel=False)
def triangulate_simple(points2d: np.ndarray,
                               camera_matrices: np.ndarray) -> np.ndarray:
    """
    Triangulate 3D point from 2D points and camera matrices using the Direct Linear Transform (DLT) method.

    :param points2d: A 2D array of shape (N, 2), where N is the number of cameras. Each row represents the
                     2D coordinates (x, y) of the point in the image plane of each camera.
    :param camera_matrices: A 3D array of shape (N, 3, 4), where each element is a 3x4 camera projection matrix.
    :return: A 1D array of shape (3,) representing the triangulated 3D point.
    """

    number_of_cameras = camera_matrices.shape[0]
    A = np.zeros((number_of_cameras * 2, 4))

    for i in range(number_of_cameras):
        x, y = points2d[i]
        mat = camera_matrices[i]
        A[i * 2] = x * mat[2] - mat[0]
        A[i * 2 + 1] = y * mat[2] - mat[1]

    _, _, vh = np.linalg.svd(A,
                             full_matrices=False)  # CHECK - Ai said this could be set to False since " we only need the right singular vectors, which is more efficient." but we should check on this bc I don't know what that means lol

    points3d_xyzh = vh[-1]
    points3d_xyzh /= points3d_xyzh[3]  # Normalize the last element to 1

    return points3d_xyzh[:3]
