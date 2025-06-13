from skellytracker.trackers.charuco_tracker.charuco_model_info import CharucoTrackingParams, CharucoModelInfo
from skellytracker.process_folder_of_videos import process_folder_of_videos
from pathlib import Path
from typing import Union
import numpy as np
from pydantic import BaseModel
class CharucoNeighborStats(BaseModel):
    mean_distance: float
    median_distance: float
    std_distance: float
    mean_error: float


def get_charuco_2d_data(calibration_videos_folder_path: Union[str, Path], num_processes: int = 1):
    return process_folder_of_videos(
        model_info=CharucoModelInfo(),
        tracking_params=CharucoTrackingParams(),
        synchronized_video_path=Path(calibration_videos_folder_path),
        num_processes=num_processes,
    )


def get_charuco_neighbor_pairs(rows: int, cols: int):
    neighbors = []
    for row in range(rows):
        for col in range(cols):
            idx = row * cols + col
            if col < cols - 1:
                neighbors.append((idx, idx + 1))  # right neighbor
            if row < rows - 1:
                neighbors.append((idx, idx + cols))  # bottom neighbor
    return neighbors


def get_neighbor_distances(
    number_of_squares_width: int, number_of_squares_height: int, charuco_3d_data: np.ndarray
) -> list:
    distances_per_frame = []
    num_cols = number_of_squares_width - 1
    num_rows = number_of_squares_height - 1

    neighbor_pairs = get_charuco_neighbor_pairs(num_rows, num_cols)

    for frame_num in range(charuco_3d_data.shape[0]):
        points_3d = charuco_3d_data[frame_num]

        # skip frames with missing points
        if np.isnan(points_3d).any():
            continue

        marker_distances = []
        for i, j in neighbor_pairs:
            pt1, pt2 = points_3d[i], points_3d[j]
            if not np.isnan(pt1).any() and not np.isnan(pt2).any():
                distance = np.linalg.norm(pt2 - pt1)
                marker_distances.append(distance)

        if marker_distances:
            distances_per_frame.append(marker_distances)
    return np.array(distances_per_frame, dtype=np.float64)


def get_neighbor_stats(distances: np.ndarray, charuco_square_size_mm: float) -> dict:
    """Computes statistics for the distances between neighboring points"""
    mean_distance = np.nanmean(distances)
    median_distance = np.nanmedian(distances)
    std_distance = np.nanstd(distances)
    mean_error = mean_distance - charuco_square_size_mm

    return CharucoNeighborStats(
        mean_distance=mean_distance, median_distance=median_distance, std_distance=std_distance, mean_error=mean_error
    )


def calculate_calibration_diagnostics(
    charuco_3d_data: np.ndarray,
    charuco_square_size_mm: float,
    number_of_squares_width: int,
    number_of_squares_height: int,
) -> CharucoNeighborStats:
    distances = get_neighbor_distances(
        number_of_squares_width=number_of_squares_width,
        number_of_squares_height=number_of_squares_height,
        charuco_3d_data=charuco_3d_data,
    )

    stats = get_neighbor_stats(distances=distances, charuco_square_size_mm=charuco_square_size_mm)
    return stats
