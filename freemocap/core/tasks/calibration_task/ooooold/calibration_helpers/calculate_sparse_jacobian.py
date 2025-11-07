import numpy as np
from scipy.sparse import dok_matrix, csr_matrix


def calculate_jacobian_sparsity(
        pixel_points2d: np.ndarray,
        ids: np.ndarray,
        num_camera_params: int
) -> csr_matrix:
    """
    Calculate the sparsity pattern of the Jacobian matrix for bundle adjustment.

    Parameters:
    - pixel_points2d (np.ndarray): CxNx2 array of 2D points where C is the number of cameras and N is the number of points.
    - ids (np.ndarray): Unique identifiers for each set of 3D points (or boards? not sure what this referred to in the og code).
    - num_camera_params (int): Number of parameters per camera.

    Returns:
    - csr_matrix: Sparse matrix representing the Jacobian sparsity pattern.
    """
    num_cameras, num_points, _ = pixel_points2d.shape

    # Initialize indices for points and cameras
    point_indices = np.arange(num_points)
    camera_indices = np.arange(num_cameras)[:, np.newaxis]

    # Mask valid (non-NaN) 2D points
    valid_points_mask = ~np.isnan(pixel_points2d).any(axis=2)

    # Remap unique IDs to a consecutive range
    def remap_ids(original_ids: np.ndarray) -> np.ndarray:
        unique_ids, remapped_ids = np.unique(original_ids, return_inverse=True)
        return remapped_ids

    remapped_ids = remap_ids(ids)
    num_boards = int(np.max(remapped_ids)) + 1
    board_params_per_board = 6  # 3 for rotation and 3 for translation
    total_board_params = num_boards * board_params_per_board

    # Calculate total parameters for reprojection and errors
    total_reprojection_params = num_cameras * num_camera_params + num_points * 3
    total_params = total_reprojection_params + total_board_params
    num_valid_points = valid_points_mask.sum()
    total_errors = num_valid_points + num_points * 3

    # Initialize sparse matrix for Jacobian
    jacobian_sparsity = dok_matrix((total_errors, total_params), dtype=bool)

    # Populate sparse matrix based on valid points
    valid_camera_indices = camera_indices[valid_points_mask]
    valid_point_indices = point_indices[valid_points_mask]

    # Update camera parameters based on reprojection error
    for param_index in range(num_camera_params):
        jacobian_sparsity[np.arange(num_valid_points), valid_camera_indices * num_camera_params + param_index] = True

    # Update point positions based on reprojection error
    for coord_index in range(3):
        jacobian_sparsity[
            np.arange(num_valid_points), num_cameras * num_camera_params + valid_point_indices * 3 + coord_index] = True

    # Update board parameters based on object points error
    for coord_index in range(3):
        for board_param_index in range(3):
            jacobian_sparsity[
                num_valid_points + point_indices * 3 + coord_index,
                total_reprojection_params + remapped_ids * 3 + board_param_index
            ] = True
            jacobian_sparsity[
                num_valid_points + point_indices * 3 + coord_index,
                total_reprojection_params + num_boards * 3 + remapped_ids * 3 + board_param_index
            ] = True

    # Update point positions based on object points error
    for coord_index in range(3):
        jacobian_sparsity[
            num_valid_points + point_indices * 3 + coord_index,
            num_cameras * num_camera_params + point_indices * 3 + coord_index
        ] = True

    # Convert to csr_matrix for efficiency in future operations
    return jacobian_sparsity.tocsr()
