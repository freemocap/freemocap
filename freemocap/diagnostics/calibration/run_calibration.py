import logging
from pathlib import Path

from freemocap.core_processes.capture_volume_calibration.run_anipose_capture_volume_calibration import (
    run_anipose_capture_volume_calibration,
)
from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration import (
    freemocap_anipose,
)
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)
from freemocap.core_processes.capture_volume_calibration.triangulate_3d_data import triangulate_3d_data
from pathlib import Path
from freemocap.data_layer.recording_models.recording_info_model import RecordingInfoModel
from freemocap.diagnostics.download_data import download_test
from freemocap.diagnostics.calibration.calibration_utils import (
    get_charuco_2d_data,
)
import numpy as np
import json

# Configure logging
logger = logging.getLogger(__name__)


class SessionInfo:
    """
    Stores paths to key processed data files.
    """

    sample_session_folder_path: str
    recording_info_model: RecordingInfoModel


def setup_session():
    """
    Downloads sample data and processes it.
    Stores all important paths for easy access.
    """
    logger.info("Downloading sample data...")

    SessionInfo.sample_session_folder_path = download_test()

    logger.info("Initializing recording model...")
    SessionInfo.recording_info_model = RecordingInfoModel(
        recording_folder_path=SessionInfo.sample_session_folder_path,
        active_tracker="mediapipe",
    )

    logger.info("Calibrating")

    board_info_path = (
        Path(SessionInfo.sample_session_folder_path) / "charuco_board_info.json"
    )  # NOTE - I added this JSON to the sample data zip file to make it easier to get square size/height/width
    with open(board_info_path, "r", encoding="utf-8") as fh:
        board_info = json.load(fh)

    charuco_square_size = board_info["square_size_mm"]
    calibration_toml_path = run_anipose_capture_volume_calibration(
        charuco_board_definition=CharucoBoardDefinition(),
        calibration_videos_folder_path=get_synchronized_video_folder_path(),
        charuco_square_size=charuco_square_size,
        progress_callback=lambda _: None,
    )

    charuco_2d_xy = get_charuco_2d_data(
        calibration_videos_folder_path=get_synchronized_video_folder_path(), num_processes=3
    )

    logger.info("Charuco 2d data detected successfully with shape: " f"{charuco_2d_xy.shape}")

    charuco_2d_xy = charuco_2d_xy.astype(np.float64)

    logger.info("Getting 3d Charuco data")
    anipose_calibration_object = freemocap_anipose.CameraGroup.load(str(calibration_toml_path))

    data_3d, *_ = triangulate_3d_data(
        anipose_calibration_object=anipose_calibration_object, image_2d_data=charuco_2d_xy
    )

    np.save(Path(SessionInfo.sample_session_folder_path) / "output_data" / "charuco_3d_xyz.npy", data_3d)

    logger.info("Session setup complete!")


def get_synchronized_video_folder_path():
    return Path(SessionInfo.recording_info_model.synchronized_videos_folder_path)


if __name__ == "__main__":
    setup_session()
