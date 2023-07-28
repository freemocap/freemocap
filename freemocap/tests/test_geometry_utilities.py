import numpy as np
import pytest

from freemocap.utilities.geometry.project_3d_data_to_z_plane import project_3d_data_to_z_plane
from freemocap.utilities.geometry.rotate_by_90_degrees_around_x_axis import rotate_by_90_degrees_around_x_axis


def test_rotate_by_90_degrees_around_x_axis():
    # test single point
    raw_skel3d_frame_marker_xyz = np.array([[[1, 2, 3]]])
    expected_result = np.array([[[1, 3, -2]]])
    assert np.allclose(
        rotate_by_90_degrees_around_x_axis(raw_skel3d_frame_marker_xyz), expected_result
    ), "Did not correctly rotate the single input point."

    # test multiple points
    raw_skel3d_frame_marker_xyz = np.array([[[1, 2, 3], [4, 5, 6], [7, 8, 9]]])
    expected_result = np.array([[[1, 3, -2], [4, 6, -5], [7, 9, -8]]])
    assert np.allclose(
        rotate_by_90_degrees_around_x_axis(raw_skel3d_frame_marker_xyz), expected_result
    ), "Did not correctly rotate the multiple input points."

    # test empty input
    raw_skel3d_frame_marker_xyz = np.array([])
    with pytest.raises(ValueError) as exc_info:
        rotate_by_90_degrees_around_x_axis(raw_skel3d_frame_marker_xyz)
    assert (
        str(exc_info.value) == "raw_skel3d_frame_marker_xyz must have shape (N, M, 3)"
    ), "Did not correctly handle an empty input array."

    # test zero input
    raw_skel3d_frame_marker_xyz = np.array([[[0, 0, 0], [0, 0, 0], [0, 0, 0]]])
    expected_result = np.array([[[0, 0, 0], [0, 0, 0], [0, 0, 0]]])
    assert np.allclose(
        rotate_by_90_degrees_around_x_axis(raw_skel3d_frame_marker_xyz), expected_result
    ), "Did not correctly handle a zero input array."


def test_project_3d_data_to_z_plane():
    # test simple case
    input_data = np.array([[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]])
    expected_output = np.array([[[1, 2, 0], [4, 5, 0]], [[7, 8, 0], [10, 11, 0]]])
    assert np.array_equal(
        project_3d_data_to_z_plane(input_data), expected_output
    ), f"Test failed for input_data: {input_data}"

    # test more complex case
    input_data = np.array(
        [
            [[7.80, 5.67, 1.72], [9.71, 9.42, 2.57]],
            [[4.85, 4.38, 3.42], [3.26, 1.13, 1.27]],
            [[3.70, 1.02, 8.64], [4.85, 5.10, 8.96]],
            [[6.57, 2.48, 2.52], [5.08, 1.76, 9.34]],
        ]
    )
    input_data_copy = np.array(
        [
            [[7.80, 5.67, 1.72], [9.71, 9.42, 2.57]],
            [[4.85, 4.38, 3.42], [3.26, 1.13, 1.27]],
            [[3.70, 1.02, 8.64], [4.85, 5.10, 8.96]],
            [[6.57, 2.48, 2.52], [5.08, 1.76, 9.34]],
        ]
    )
    expected_output = np.array(
        [
            [[7.80, 5.67, 0], [9.71, 9.42, 0]],
            [[4.85, 4.38, 0], [3.26, 1.13, 0]],
            [[3.70, 1.02, 0], [4.85, 5.10, 0]],
            [[6.57, 2.48, 0], [5.08, 1.76, 0]],
        ]
    )
    assert np.array_equal(
        project_3d_data_to_z_plane(input_data), expected_output
    ), f"Test failed for input_data: {input_data}"

    # test input data was not changed
    assert np.array_equal(
        input_data, input_data_copy
    ), "Input data was modified by function, function should not change the input data."
