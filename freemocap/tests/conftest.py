import pytest

from freemocap.core_processes.process_motion_capture_videos.process_recording_headless import (
    process_recording_headless,
    find_calibration_toml_path,
)
from freemocap.data_layer.recording_models.recording_info_model import RecordingInfoModel
from freemocap.utilities.download_sample_data import (
    download_sample_data,
)

class SessionInfo:
    sample_session_folder_path: str
    recording_info_model: RecordingInfoModel

def pytest_sessionstart():
    SessionInfo.sample_session_folder_path = download_sample_data()
    calibration_toml_path = find_calibration_toml_path(SessionInfo.sample_session_folder_path)
    SessionInfo.recording_info_model = RecordingInfoModel(
        recording_folder_path=SessionInfo.sample_session_folder_path, active_tracker="mediapipe"
    )
    # TODO: make this configurable to be able to take different trackers
    process_recording_headless(
        recording_path=SessionInfo.sample_session_folder_path,
        path_to_camera_calibration_toml=calibration_toml_path,
        recording_info_model=SessionInfo.recording_info_model,
        run_blender=False,
        make_jupyter_notebook=False,
        use_tqdm=False,
    )


@pytest.fixture
def sample_session_path():
    return SessionInfo.sample_session_folder_path


@pytest.fixture
def synchronized_video_folder_path():
    return SessionInfo.recording_info_model.synchronized_videos_folder_path


@pytest.fixture
def data_folder_path():
    return SessionInfo.recording_info_model.output_data_folder_path


@pytest.fixture
def raw_skeleton_data():
    return SessionInfo.recording_info_model.raw_data_3d_npy_file_path


@pytest.fixture
def total_body_center_of_mass_data():
    return SessionInfo.recording_info_model.total_body_center_of_mass_npy_file_path


@pytest.fixture
def image_tracking_data():
    return SessionInfo.recording_info_model.data_2d_npy_file_path


@pytest.fixture
def reprojection_error_data():
    return SessionInfo.recording_info_model.reprojection_error_data_npy_file_path


if __name__ == "__main__":
    pytest_sessionstart()
