from pathlib import Path
import numpy as np
from time import perf_counter_ns

from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.freemocap_anipose import CameraGroup


if __name__ == "__main__":
    # TODO: do all this setup with recording_info object
    recording_folder = Path("/Users/philipqueen/freemocap_data/recording_sessions/freemocap_test_data/")

    calibration_toml_path = list(recording_folder.glob("*calibration.toml"))[0]
    calibration = CameraGroup.load(calibration_toml_path)

    data_2d_path = (
        recording_folder
        / "output_data"
        / "raw_data"
        / "mediapipe_2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy"
    )
    data_2d = np.load(data_2d_path)
    data_2d_flat = data_2d.reshape(data_2d.shape[0], -1, 2)

    data_3d = calibration.triangulate(data_2d_flat, progress=False)
    print(f"data_3d shape: {data_3d.shape}")
    print(f"data_2d_flat shape: {data_2d_flat.shape}")

    num_trials = 5

    print("Benchmarking reprojection error with mean=True:\n")
    times = []
    for i in range(num_trials):
        start = perf_counter_ns()
        calibration.reprojection_error(points_3d=data_3d, points_2d=data_2d_flat, mean=True)
        end = perf_counter_ns()
        times.append((end - start) / 1e9)
        print(f"This round reprojection error time is: {(end - start) / 1e9} seconds for {data_2d.shape[1]} frames")
        print(f"This round average time per frame is: {(end - start) / 1e9 / data_2d.shape[1]} seconds\n")

    print(
        f"\tAverage reprojection error time across trials is: {np.mean(times)} seconds for {data_2d.shape[1]} frames over {num_trials} runs"
    )
    print(f"\tAverage time per frame is: {np.mean(times) / (data_2d.shape[1] * num_trials)} seconds\n")

    print("Benchmarking reprojection error with mean=False:\n")
    times = []
    for i in range(num_trials):
        start = perf_counter_ns()
        calibration.reprojection_error(points_3d=data_3d, points_2d=data_2d_flat, mean=False)
        end = perf_counter_ns()
        times.append((end - start) / 1e9)
        print(f"This round reprojection error time is: {(end - start) / 1e9} seconds for {data_2d.shape[1]} frames")
        print(f"This round average time per frame is: {(end - start) / 1e9 / data_2d.shape[1]} seconds\n")
    print(
        f"\tAverage reprojection error time across trials is: {np.mean(times)} seconds for {data_2d.shape[1]} frames over {num_trials} runs"
    )
    print(f"\tAverage time per frame is: {np.mean(times) / (data_2d.shape[1] * num_trials)} seconds\n")
