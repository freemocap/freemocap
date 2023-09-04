from pathlib import Path
from typing import Union

from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.anipose_camera_calibrator import (
    AniposeCameraCalibrator,
)
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)


def headless_calibration(
    path_to_folder_of_calibration_videos: Path,
    charuco_board_object=CharucoBoardDefinition,
    charuco_square_size: Union[int, float] = 39,
    pin_camera_0_to_origin: bool = True,
):
    anipose_camera_calibrator = AniposeCameraCalibrator(
        charuco_board_object=charuco_board_object,
        charuco_square_size=charuco_square_size,
        calibration_videos_folder_path=path_to_folder_of_calibration_videos,
        progress_callback=lambda *args, **kwargs: None,  # the empty callable is needed, otherwise calibration will cause an error
    )

    anipose_camera_calibrator.calibrate_camera_capture_volume(pin_camera_0_to_origin=pin_camera_0_to_origin)


if __name__ == "__main__":
    path_to_folder_of_calibration_videos = Path("/PATH/TO/CALIBRATION/VIDEOS")
    charuco_square_size = 110  # size of a black square on your charuco board in mm

    headless_calibration(
        path_to_folder_of_calibration_videos=path_to_folder_of_calibration_videos,
        charuco_square_size=charuco_square_size,
    )
