import csv
import json
import platform
from pathlib import Path

import numpy as np

from freemocap.diagnostics.calibration.calibration_utils import (
    CharucoNeighborStats, get_neighbor_distances, get_neighbor_stats)


def run(path_to_recording: Path):

    path_to_3d_data = path_to_recording / "output_data" / "charuco_3d_xyz.npy"
    charuco_3d_data = np.load(path_to_3d_data)
    csv_save_path = Path("data_current_calibration.csv")

    path_to_json = path_to_recording / "charuco_board_info.json"
    with open(path_to_json, "r", encoding="utf-8") as fh:
        charuco_board_info = json.load(fh)

    charuco_square_size_mm = charuco_board_info["square_size_mm"]
    number_of_squares_height = charuco_board_info["num_squares_height"]
    number_of_squares_width = charuco_board_info["num_squares_width"]

    distances_between_squares = get_neighbor_distances(
        charuco_3d_data=charuco_3d_data,
        number_of_squares_width=number_of_squares_width,
        number_of_squares_height=number_of_squares_height,
    )

    square_stats: CharucoNeighborStats = get_neighbor_stats(
        distances=distances_between_squares, charuco_square_size_mm=charuco_square_size_mm
    )

    raw_os = platform.system()
    os_map = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}
    os_name = os_map.get(raw_os, raw_os)

    row = {
        "os": os_name,  # Windows / Linux / Darwin
        "version": "current",  # tag for this run
        "mean_distance": square_stats.mean_distance,
        "median_distance": square_stats.median_distance,
        "std_distance": square_stats.std_distance,
        "mean_error": square_stats.mean_error,
    }

    with open(csv_save_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=row.keys())
        writer.writeheader()
        writer.writerow(row)

    print(f"✅ one-row CSV written → {csv_save_path}")


if __name__ == "__main__":
    # Use environment detection to handle different runners
    import sys

    if sys.platform.startswith("win"):
        path_to_recording = Path(r"C:\Users\runneradmin\freemocap_data\recording_sessions\freemocap_test_data")
    elif sys.platform.startswith("linux"):
        path_to_recording = Path("/home/runner/freemocap_data/recording_sessions/freemocap_test_data")
    elif sys.platform.startswith("darwin"):
        path_to_recording = Path("/Users/runner/freemocap_data/recording_sessions/freemocap_test_data")
    else:
        raise RuntimeError(f"Unsupported OS: {sys.platform}")

    run(path_to_recording=path_to_recording)
