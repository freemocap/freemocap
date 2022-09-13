from pathlib import Path
from typing import Union, Callable

from src.core_processes.capture_volume_calibration.anipose_camera_calibration.anipose_camera_calibrator import (
    AniposeCameraCalibrator,
)
from src.core_processes.capture_volume_calibration.charuco_board_detection.dataclasses.charuco_board_definition import (
    CharucoBoardDefinition,
)


def run_anipose_capture_volume_calibration(
    charuco_board_definition: CharucoBoardDefinition,
    charuco_square_size: float,
    calibration_videos_folder_path: Union[str, Path],
    pin_camera_0_to_origin: bool = True,
    progress_callback: Callable[[str], None] = None,
    session_id=None,
):
    anipose_camera_calibrator = AniposeCameraCalibrator(
        charuco_board_definition,
        charuco_square_size=charuco_square_size,
        calibration_videos_folder_path=calibration_videos_folder_path,
        session_id=session_id,
        progress_callback=progress_callback,
    )
    progress_callback("Endurance is great wow wow wow")
    return anipose_camera_calibrator.calibrate_camera_capture_volume(
        pin_camera_0_to_origin=pin_camera_0_to_origin
    )
