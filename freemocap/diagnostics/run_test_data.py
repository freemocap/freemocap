import logging
from pathlib import Path

from freemocap.core_processes.process_motion_capture_videos.process_recording_headless import (
    process_recording_headless,
    find_calibration_toml_path,
)
from freemocap.data_layer.recording_models.recording_info_model import RecordingInfoModel
from freemocap.utilities.download_sample_data import download_sample_data

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
    # SessionInfo.sample_session_folder_path = Path(r'/home/runner/work/freemocap_fork/freemocap_fork/freemocap/freemocap_test_data')
    SessionInfo.sample_session_folder_path = download_sample_data(sample_data_zip_file_url='https://github.com/aaroncherian/freemocap_fork/releases/download/v0.0.1-alpha/freemocap_test_data.zip')

    logger.info("Finding calibration file...")
    calibration_toml_path = find_calibration_toml_path(SessionInfo.sample_session_folder_path)

    logger.info("Initializing recording model...")
    SessionInfo.recording_info_model = RecordingInfoModel(
        recording_folder_path=SessionInfo.sample_session_folder_path,
        active_tracker="mediapipe",
    )

    logger.info("Processing motion capture data...")
    process_recording_headless(
        recording_path=SessionInfo.sample_session_folder_path,
        path_to_camera_calibration_toml=calibration_toml_path,
        recording_info_model=SessionInfo.recording_info_model,
        run_blender=False,
        make_jupyter_notebook=False,
        use_tqdm=False,
    )

    logger.info("Session setup complete!")

def get_sample_session_path():
    return Path(SessionInfo.sample_session_folder_path)

def get_synchronized_video_folder_path():
    return Path(SessionInfo.recording_info_model.synchronized_videos_folder_path)

def get_data_folder_path():
    return Path(SessionInfo.recording_info_model.output_data_folder_path)

def get_raw_skeleton_data():
    return Path(SessionInfo.recording_info_model.raw_data_3d_npy_file_path)

def get_total_body_center_of_mass_data():
    return Path(SessionInfo.recording_info_model.total_body_center_of_mass_npy_file_path)

def get_image_tracking_data():
    return Path(SessionInfo.recording_info_model.data_2d_npy_file_path)

def get_reprojection_error_data():
    return Path(SessionInfo.recording_info_model.reprojection_error_data_npy_file_path)

# Run setup if executed directly
if __name__ == "__main__":
    setup_session()
