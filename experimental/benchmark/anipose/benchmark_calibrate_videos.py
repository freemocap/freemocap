from pathlib import Path
import numpy as np
from time import perf_counter_ns

from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.freemocap_anipose import (
    CameraGroup,
    AniposeCharucoBoard,
)
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)
from freemocap.utilities.get_video_paths import get_video_paths


if __name__ == "__main__":
    # TODO: do all this setup with recording_info object
    recording_folder = Path("/Users/philipqueen/freemocap_data/recording_sessions/freemocap_test_data/")
    synchronized_folder = recording_folder / "synchronized_videos"

    video_paths = get_video_paths(synchronized_folder)
    list_of_camera_names = [video_path.stem for video_path in video_paths]
    video_paths_list_of_list_of_strings = [[str(this_path)] for this_path in video_paths]

    calibration = CameraGroup.from_names(list_of_camera_names)
    charuco_square_size = 39

    calibration.metadata["charuco_square_size"] = charuco_square_size
    calibration.metadata["charuco_board_object"] = str(CharucoBoardDefinition)
    calibration.metadata["path_to_recorded_videos"] = str(synchronized_folder)
    calibration.metadata["date_time_calibrated"] = str(np.datetime64("now"))

    anipose_charuco_board = AniposeCharucoBoard(
        7,
        6,
        square_length=charuco_square_size,  # mm
        marker_length=charuco_square_size * 0.8,
        marker_bits=4,
        dict_size=250,
    )

    num_trials = 5
    print("Benchmarking calibrate_videos:\n")
    times = []
    for i in range(num_trials):
        start = perf_counter_ns()
        calibration.calibrate_videos(video_paths_list_of_list_of_strings, anipose_charuco_board)
        end = perf_counter_ns()
        times.append((end - start) / 1e9)
        print(f"This round calibration time is: {(end - start) / 1e9} seconds")
    print(f"\tAverage calibration time across trials is: {np.mean(times)} seconds over {num_trials} runs")
