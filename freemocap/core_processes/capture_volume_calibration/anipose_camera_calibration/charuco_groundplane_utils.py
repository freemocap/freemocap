import numpy as np


def get_unit_vector(vector: np.ndarray) -> np.ndarray:
    return vector / np.linalg.norm(vector)


def compute_basis(charuco_frame: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_vec = charuco_frame[18] - charuco_frame[0]
    y_vec = charuco_frame[5] - charuco_frame[0]

    x_hat = get_unit_vector(x_vec)
    y_hat_raw = get_unit_vector(y_vec)
    z_hat = get_unit_vector(np.cross(x_hat, y_hat_raw))
    y_hat = get_unit_vector(np.cross(z_hat, x_hat))

    return x_hat, y_hat, z_hat
