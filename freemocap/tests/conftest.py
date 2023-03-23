import pytest

from freemocap.tests.utilities.import_sample_data import (
    load_sample_data,
    find_data_folder_path,
    find_skeleton_npy_file_name,
    find_synchronized_videos_folder_path,
    find_image_data_file_name,
    find_reprojection_error_file_name,
    find_total_body_center_of_mass_file_name,
)

sample_session_folder_path = load_sample_data()


@pytest.fixture
def sample_session_path():
    return sample_session_folder_path


@pytest.fixture
def synchronized_video_folder_path():
    return find_synchronized_videos_folder_path(sample_session_folder_path)


@pytest.fixture
def data_folder_path():
    return find_data_folder_path(sample_session_folder_path)


@pytest.fixture
def skeleton_npy_file_path():
    return find_skeleton_npy_file_name(find_data_folder_path(sample_session_folder_path))


@pytest.fixture
def total_body_center_of_mass_file_path():
    return find_total_body_center_of_mass_file_name(find_data_folder_path(sample_session_folder_path))


@pytest.fixture
def image_data_file_name():
    return find_image_data_file_name(find_data_folder_path(sample_session_folder_path))


@pytest.fixture
def reprojection_error_file_name():
    return find_reprojection_error_file_name(find_data_folder_path(sample_session_folder_path))