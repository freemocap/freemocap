import numpy as np
from skellytracker.trackers.charuco_tracker.charuco_model_info import CharucoTrackingParams, CharucoModelInfo
from skellytracker.process_folder_of_videos import process_folder_of_videos
from pathlib import Path
from typing import Union


def get_unit_vector(vector: np.ndarray) -> np.ndarray:
    return vector / np.linalg.norm(vector)


def compute_basis_vectors_of_new_reference(charuco_frame: np.ndarray,
                                           number_of_squares_width: int,
                                           number_of_squares_height: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    num_cols = number_of_squares_width - 1  # corner columns
    num_rows = number_of_squares_height - 1  # corner rows

    origin = charuco_frame[0]
    idx_x = num_cols * (num_rows - 1)
    idx_y = num_cols - 1

    x_vec = charuco_frame[idx_x] - origin
    y_vec = charuco_frame[idx_y] - origin

    x_hat = get_unit_vector(x_vec)
    y_hat_raw = get_unit_vector(y_vec)
    z_hat = get_unit_vector(np.cross(x_hat, y_hat_raw))
    y_hat = get_unit_vector(np.cross(z_hat, x_hat))

    return x_hat, y_hat, z_hat


def get_charuco_frame(charuco_3d_data: np.ndarray):
    return charuco_3d_data[10, :, :]
