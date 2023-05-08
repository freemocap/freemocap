import pytest

from freemocap.tests.utilities.import_sample_data import (
    load_sample_data,
    find_data_folder_path,
    find_raw_skeleton_npy_file_name,
    find_synchronized_videos_folder_path,
    find_image_tracking_data_file_name,
    find_reprojection_error_file_name,
    find_total_body_center_of_mass_file_name,
)
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
    return find_synchronized_videos_folder_path(pytest.sample_session_folder_path)


@pytest.fixture
def data_folder_path():
    return find_data_folder_path(pytest.sample_session_folder_path)


@pytest.fixture
def raw_skeleton_npy_file_path():
    return find_raw_skeleton_npy_file_name(find_data_folder_path(pytest.sample_session_folder_path))


@pytest.fixture
def total_body_center_of_mass_file_path():
    return find_total_body_center_of_mass_file_name(find_data_folder_path(pytest.sample_session_folder_path))


@pytest.fixture
def image_tracking_data_file_name():
    return find_image_tracking_data_file_name(find_data_folder_path(pytest.sample_session_folder_path))


@pytest.fixture
def reprojection_error_file_name():
    return find_reprojection_error_file_name(find_data_folder_path(pytest.sample_session_folder_path))
