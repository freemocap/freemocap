from pathlib import Path
from typing import Union

from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.anipose_camera_calibrator import (
    AniposeCameraCalibrator,
)
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition, charuco_5x3, charuco_7x5
)


def headless_calibration(
        path_to_folder_of_calibration_videos: Path,
        charuco_board_object: CharucoBoardDefinition = charuco_7x5(),
        charuco_square_size: Union[int, float] = 39,
        pin_camera_0_to_origin: bool = True,
        use_charuco_as_groundplane: bool = False
):
    anipose_camera_calibrator = AniposeCameraCalibrator(
        charuco_board_object=charuco_board_object,
        charuco_square_size=charuco_square_size,
        calibration_videos_folder_path=path_to_folder_of_calibration_videos,
        progress_callback=lambda *args, **kwargs: None,
        # the empty callable is needed, otherwise calibration will cause an error
    )

    toml_path, groundplane_success = anipose_camera_calibrator.calibrate_camera_capture_volume(
        pin_camera_0_to_origin=pin_camera_0_to_origin,
        use_charuco_as_groundplane=use_charuco_as_groundplane,
    )

    print(f"Camera calibration saved to: {toml_path}")
    print(f"Ground plane calibration success: {groundplane_success}")


if __name__ == "__main__":
    path_to_folder_of_calibration_videos = Path(r"C:\Users\aaron\freemocap_data\recording_sessions\freemocap_test_data\synchronized_videos")
    charuco_square_size = 57  # size of a black square on your charuco board in mm
    # charuco_definition = charuco_7x5()
    charuco_definition = charuco_5x3()

    use_charuco_as_groundplane = True

    headless_calibration(
        path_to_folder_of_calibration_videos=path_to_folder_of_calibration_videos,
        charuco_board_object=charuco_definition,
        charuco_square_size=charuco_square_size,
        pin_camera_0_to_origin=True,
        use_charuco_as_groundplane=use_charuco_as_groundplane
    )
