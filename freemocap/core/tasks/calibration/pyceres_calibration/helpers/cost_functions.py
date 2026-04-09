"""Pyceres cost functions for camera calibration bundle adjustment.

Each cost function connects parameter blocks (camera extrinsics, intrinsics,
board poses) to observed pixel measurements via the camera projection model.
"""

import numpy as np
import pyceres
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation


# =============================================================================
# PROJECTION HELPERS
# =============================================================================


def _quat_wxyz_to_rotation_matrix(quat_wxyz: NDArray[np.float64]) -> NDArray[np.float64]:
    """Convert [w, x, y, z] quaternion to 3x3 rotation matrix."""
    w, x, y, z = quat_wxyz
    return Rotation.from_quat([x, y, z, w]).as_matrix()


def _project_point(
    *,
    point_camera: NDArray[np.float64],
    intrinsics: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Project a 3D point (in camera frame) to 2D pixel coordinates.

    Uses the OpenCV camera model with radial + tangential distortion.

    Args:
        point_camera: (3,) point in camera coordinates [X, Y, Z]
        intrinsics: (8,) array [fx, fy, cx, cy, k1, k2, p1, p2]

    Returns:
        (2,) projected pixel coordinates [u, v]
    """
    fx, fy, cx, cy, k1, k2, p1, p2 = intrinsics

    X, Y, Z = point_camera
    x = X / Z
    y = Y / Z

    r2 = x * x + y * y
    radial = 1.0 + k1 * r2 + k2 * r2 * r2
    x_dist = x * radial + 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x * x)
    y_dist = y * radial + p1 * (r2 + 2.0 * y * y) + 2.0 * p2 * x * y

    u = fx * x_dist + cx
    v = fy * y_dist + cy

    return np.array([u, v], dtype=np.float64)


# =============================================================================
# REPROJECTION COST
# =============================================================================


class CharucoReprojectionCost(pyceres.CostFunction):
    """Reprojection error for a single observed charuco corner.

    Transforms a known board corner through the board pose and camera model,
    and computes the pixel-space residual against the observed 2D detection.

    Pipeline:
        1. p_world = R_board @ p_board + t_board
        2. p_cam   = R_cam   @ p_world + t_cam
        3. p_2d    = project(intrinsics, p_cam)
        4. residual = weight * (observed_2d - p_2d)

    Parameter blocks:
        [0] cam_quaternion_wxyz  (4)
        [1] cam_translation      (3)
        [2] cam_intrinsics       (8) [fx, fy, cx, cy, k1, k2, p1, p2]
        [3] board_quaternion_wxyz (4)
        [4] board_translation     (3)

    Residuals: 2 (pixel x error, pixel y error)
    """

    def __init__(
        self,
        *,
        observed_pixel: NDArray[np.float64],
        board_point_3d: NDArray[np.float64],
        weight: float = 1.0,
    ) -> None:
        super().__init__()
        self.observed_pixel = observed_pixel.copy().astype(np.float64)
        self.board_point_3d = board_point_3d.copy().astype(np.float64)
        self.weight = weight
        self.set_num_residuals(2)
        self.set_parameter_block_sizes([4, 3, 8, 4, 3])

    def Evaluate(
        self,
        parameters: list[NDArray[np.float64]],
        residuals: NDArray[np.float64],
        jacobians: list[NDArray[np.float64]] | None,
    ) -> bool:
        cam_quat = parameters[0]
        cam_trans = parameters[1]
        intrinsics = parameters[2]
        board_quat = parameters[3]
        board_trans = parameters[4]

        # Board-local → world
        R_board = _quat_wxyz_to_rotation_matrix(board_quat)
        p_world = R_board @ self.board_point_3d + board_trans

        # World → camera
        R_cam = _quat_wxyz_to_rotation_matrix(cam_quat)
        p_cam = R_cam @ p_world + cam_trans

        # Camera → pixel
        if p_cam[2] <= 1e-6:
            residuals[:] = 0.0
            if jacobians is not None:
                for j_idx in range(5):
                    if jacobians[j_idx] is not None:
                        jacobians[j_idx][:] = 0.0
            return True

        projected = _project_point(point_camera=p_cam, intrinsics=intrinsics)
        residuals[:] = self.weight * (self.observed_pixel - projected)

        # Numerical Jacobians
        if jacobians is not None:
            eps = 1e-8
            block_sizes = [4, 3, 8, 4, 3]

            for block_idx in range(5):
                if jacobians[block_idx] is None:
                    continue

                block_size = block_sizes[block_idx]
                params_copy = [p.copy() for p in parameters]

                for j in range(block_size):
                    params_copy[block_idx] = parameters[block_idx].copy()
                    params_copy[block_idx][j] += eps

                    # Re-normalize quaternions after perturbation
                    if block_idx in (0, 3):
                        params_copy[block_idx] /= np.linalg.norm(params_copy[block_idx])

                    # Recompute forward pass
                    R_b = _quat_wxyz_to_rotation_matrix(params_copy[3])
                    pw = R_b @ self.board_point_3d + params_copy[4]
                    R_c = _quat_wxyz_to_rotation_matrix(params_copy[0])
                    pc = R_c @ pw + params_copy[1]

                    if pc[2] <= 1e-6:
                        for i in range(2):
                            jacobians[block_idx][i * block_size + j] = 0.0
                    else:
                        proj_plus = _project_point(point_camera=pc, intrinsics=params_copy[2])
                        res_plus = self.weight * (self.observed_pixel - proj_plus)
                        for i in range(2):
                            jacobians[block_idx][i * block_size + j] = (
                                (res_plus[i] - residuals[i]) / eps
                            )

        return True


# =============================================================================
# INTRINSICS PRIOR
# =============================================================================


class IntrinsicsPriorCost(pyceres.CostFunction):
    """Soft prior penalizing intrinsics drift from initial estimates.

    Acts as Gaussian regularization: cost = weight * (current - initial).
    Prevents intrinsic parameters from wandering into physically implausible
    regions when observation data is sparse.

    Parameter blocks:
        [0] cam_intrinsics (8) [fx, fy, cx, cy, k1, k2, p1, p2]

    Residuals: 8 (one per intrinsic parameter)
    """

    def __init__(
        self,
        *,
        initial_intrinsics: NDArray[np.float64],
        weight: float = 0.01,
    ) -> None:
        super().__init__()
        self.initial = initial_intrinsics.copy().astype(np.float64)
        if self.initial.shape != (8,):
            raise ValueError(f"Expected shape (8,), got {self.initial.shape}")
        self.weight = weight
        self.set_num_residuals(8)
        self.set_parameter_block_sizes([8])

    def Evaluate(
        self,
        parameters: list[NDArray[np.float64]],
        residuals: NDArray[np.float64],
        jacobians: list[NDArray[np.float64]] | None,
    ) -> bool:
        residuals[:] = self.weight * (parameters[0] - self.initial)

        if jacobians is not None and jacobians[0] is not None:
            # Jacobian is diagonal: d(residual_i)/d(param_j) = weight * delta_ij
            # Stored in row-major: jacobians[0][i * 8 + j]
            jacobians[0][:] = 0.0
            for i in range(8):
                jacobians[0][i * 8 + i] = self.weight

        return True
