from pathlib import Path
from typing import Callable, Union

from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.anipose_camera_calibrator import (
    AniposeCameraCalibrator,
)
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)


async def async_run_anipose_capture_volume_calibration(**kwargs):
    run_anipose_capture_volume_calibration(**kwargs)


def run_anipose_capture_volume_calibration(
    charuco_board_definition: CharucoBoardDefinition,
    charuco_square_size: float,
    calibration_videos_folder_path: Union[str, Path],
    pin_camera_0_to_origin: bool = True,
    progress_callback: Callable[[str], None] = None,
):
    anipose_camera_calibrator = AniposeCameraCalibrator(
        charuco_board_definition,
        charuco_square_size=charuco_square_size,
        calibration_videos_folder_path=calibration_videos_folder_path,
        progress_callback=progress_callback,
    )
    progress_callback("Endurance is great wow wow wow")
    anipose_camera_calibrator.calibrate_camera_capture_volume(pin_camera_0_to_origin=pin_camera_0_to_origin)
