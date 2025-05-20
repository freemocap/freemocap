import numpy as np
from skellytracker.trackers.charuco_tracker.charuco_model_info import CharucoTrackingParams, CharucoModelInfo
from skellytracker.process_folder_of_videos import process_folder_of_videos
from pathlib import Path
from typing import Union

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


def get_charuco_2d_data(calibration_videos_folder_path: Union[str, Path],
                        num_processes: int = 1) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    charuco_2d_xy = process_folder_of_videos(
                model_info=CharucoModelInfo(),
                tracking_params=CharucoTrackingParams(),
                synchronized_video_path=Path(calibration_videos_folder_path),
                num_processes=num_processes
            )

