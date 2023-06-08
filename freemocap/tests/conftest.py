import pytest

from freemocap.tests.utilities.load_sample_data import (
    load_sample_data,
)
from freemocap.system.paths_and_filenames.path_getters import get_output_data_folder_path, \
    get_synchronized_videos_folder_path, get_raw_skeleton_npy_file_name, get_total_body_center_of_mass_file_name, \
    get_image_tracking_data_file_name, get_reprojection_error_file_name
from freemocap.tests.utilities.process_recording_headless import process_recording_headless, find_calibration_toml_path


def pytest_sessionstart():
    pytest.sample_session_folder_path = load_sample_data()
    calibration_toml_path = find_calibration_toml_path(pytest.sample_session_folder_path)
    process_recording_headless(
        recording_path=pytest.sample_session_folder_path, path_to_camera_calibration_toml=calibration_toml_path
    )


@pytest.fixture
def sample_session_path():
    return pytest.sample_session_folder_path


@pytest.fixture
def synchronized_video_folder_path():
    return get_synchronized_videos_folder_path(pytest.sample_session_folder_path)


@pytest.fixture
def data_folder_path():
    return get_output_data_folder_path(pytest.sample_session_folder_path)


@pytest.fixture
def raw_skeleton_npy_file_path():
    return get_raw_skeleton_npy_file_name(get_output_data_folder_path(pytest.sample_session_folder_path))


@pytest.fixture
def total_body_center_of_mass_file_path():
    return get_total_body_center_of_mass_file_name(get_output_data_folder_path(pytest.sample_session_folder_path))


@pytest.fixture
def image_tracking_data_file_name():
    return get_image_tracking_data_file_name(get_output_data_folder_path(pytest.sample_session_folder_path))


@pytest.fixture
def reprojection_error_file_name():
    return get_reprojection_error_file_name(get_output_data_folder_path(pytest.sample_session_folder_path))

if __name__ == "__main__":
    pytest_sessionstart()