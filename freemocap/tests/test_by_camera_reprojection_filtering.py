import numpy as np

from freemocap.core_processes.capture_volume_calibration.by_camera_reprojection_filtering import (
    _get_camera_frame_marker_lists_to_reproject,
    _set_unincluded_data_to_nans,
)


def test_get_camera_frame_marker_lists_to_reproject():
    # test removing one camera
    reprojError_cam_frame_marker = np.array(
        [[[1, 5, 3], [4, 5, 6], [7, 8, 9]], [[2, 3, 4], [5, 6, 9], [8, 9, 10]], [[3, 6, 5], [6, 7, 8], [9, 10, 11]]]
    )
    frame_marker_list = [(0, 1), (1, 2)]
    num_cameras_to_remove = 1
    expected_output = ([[2], [1]], [0, 1], [1, 2])
    assert (
        _get_camera_frame_marker_lists_to_reproject(
            reprojError_cam_frame_marker, frame_marker_list, num_cameras_to_remove
        )
        == expected_output
    )
    # test removing two cameras
    frame_marker_list = [(0, 1), (1, 2)]
    num_cameras_to_remove = 2
    expected_output = ([[2, 0], [1, 2]], [0, 1], [1, 2])
    assert (
        _get_camera_frame_marker_lists_to_reproject(
            reprojError_cam_frame_marker, frame_marker_list, num_cameras_to_remove
        )
        == expected_output
    )
    # test removing all cameras
    frame_marker_list = [(0, 1), (1, 2)]
    num_cameras_to_remove = 3
    expected_output = ([[2, 0, 1], [1, 2, 0]], [0, 1], [1, 2])
    assert (
        _get_camera_frame_marker_lists_to_reproject(
            reprojError_cam_frame_marker, frame_marker_list, num_cameras_to_remove
        )
        == expected_output
    )
    # test removing more cameras than dimensions
    frame_marker_list = [(0, 1), (1, 2)]
    num_cameras_to_remove = 4
    # should just return all of the camera sorted by max reprojection error, no need to error
    expected_output = ([[2, 0, 1], [1, 2, 0]], [0, 1], [1, 2])
    assert (
        _get_camera_frame_marker_lists_to_reproject(
            reprojError_cam_frame_marker, frame_marker_list, num_cameras_to_remove
        )
        == expected_output
    )
    # test providing no frames or markers
    frame_marker_list = []
    num_cameras_to_remove = 2
    expected_output = ([], [], [])
    assert (
        _get_camera_frame_marker_lists_to_reproject(
            reprojError_cam_frame_marker, frame_marker_list, num_cameras_to_remove
        )
        == expected_output
    )


def test_set_unincluded_data_to_nans():
    # test indices are turned to nans
    data = np.random.rand(5, 5, 5, 2)
    frames_with_reprojection_error = [1, 2]
    markers_with_reprojection_error = [3, 4]
    cameras_to_remove = [[0, 1], [2, 3]]
    result = _set_unincluded_data_to_nans(data, frames_with_reprojection_error, markers_with_reprojection_error, cameras_to_remove)
    for cameras, frame, marker in zip(cameras_to_remove, frames_with_reprojection_error, markers_with_reprojection_error):
        for camera in cameras:
            np.testing.assert_array_equal(result[camera, frame, marker, :], np.full((2,), np.nan))

    # test other indices aren't touched
    data = np.random.rand(5, 5, 5, 2)
    frames_with_reprojection_error = [1, 2]
    markers_with_reprojection_error = [3, 4]
    cameras_to_remove = [[0, 1], [2, 3]]
    original_data = data.copy()
    result = _set_unincluded_data_to_nans(data, frames_with_reprojection_error, markers_with_reprojection_error, cameras_to_remove)
    mask = np.ones(data.shape, dtype=bool)
    for cameras, frame, marker in zip(cameras_to_remove, frames_with_reprojection_error, markers_with_reprojection_error):
        for camera in cameras:
            mask[camera, frame, marker, :] = False
    np.testing.assert_array_equal(result[mask], original_data[mask])


if __name__ == "__main__":
    test_get_camera_frame_marker_lists_to_reproject()
