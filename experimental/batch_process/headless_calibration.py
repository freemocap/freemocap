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
        use_charuco_as_groundplane: bool = False,
        recording_name: str | None = None
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
        recording_name=recording_name
    )

    print(f"Camera calibration saved to: {toml_path}")
    print(f"Ground plane calibration success: {groundplane_success}")


if __name__ == "__main__":
    import sys
    path_to_folder_of_calibration_videos = Path("")
    charuco_square_size = 57  # size of a black square on your charuco board in mm
    charuco_definition = charuco_7x5()
    # charuco_definition = charuco_5x3()

    use_charuco_as_groundplane = False

    recording_name = "headless_calibration" # change this is any string, or to None for default

    args = sys.argv[1:]

    if len(args > 0):
        path_to_folder_of_calibration_videos = Path(args[0])

    if not path_to_folder_of_calibration_videos.exists():
        print(f"Error: Directory does not exist: {path_to_folder_of_calibration_videos}")
        print("\nUsage: python headless_calibration.py [path_to_folder_of_calibration_videos]"
            "[--recording_name NAME] [--square-size MM] {--7x5 | --5x3} {--use-groundplane | --no-groundplane}")
        sys.exit(1)

    if "--recording-name" in args:
        recording_name = args[args.index("--recording-name") + 1]

    if "--square-size" in args:
        charuco_square_size = float(args[args.index("--square-size") + 1])

    if "--7x5" in args:
        charuco_definition = charuco_7x5()
    elif "--5x3" in args:
        charuco_definition = charuco_5x3()

    if "--use-groundplane" in args:
        use_charuco_as_groundplane = True
    elif "--no-groundplane" in args:
        use_charuco_as_groundplane = False


    headless_calibration(
        path_to_folder_of_calibration_videos=path_to_folder_of_calibration_videos,
        charuco_board_object=charuco_definition,
        charuco_square_size=charuco_square_size,
        pin_camera_0_to_origin=True,
        use_charuco_as_groundplane=use_charuco_as_groundplane,
        recording_name=recording_name
    )