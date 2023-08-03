import numpy as np

from freemocap.core_processes.capture_volume_calibration.reprojection_filtering import (
    find_frames_with_reprojection_error_above_limit,
    set_unincluded_data_to_nans,
)


def test_find_frames_with_reprojection_error_above_limit():
    # test reprojection error threshold is 0.5
    reprojection_error_threshold = 0.5
    reprojection_error_frames_markers = np.array(
        [
            [0.1, 0.2, 0.3],  # Mean reprojection error = 0.2
            [0.4, 0.5, 0.6],  # Mean reprojection error = 0.5
            [0.7, 0.8, 0.9],  # Mean reprojection error = 0.8
        ]
    )
    expected_output = [2]  # Only the third frame has reprojection error above 0.5
    assert (
        find_frames_with_reprojection_error_above_limit(
            reprojection_error_threshold,
            reprojection_error_frames_markers,
        )
        == expected_output
    ), "Did not find correct frames with reprojection error above threshold"

    # test reprojection error threshold is 0.8
    reprojection_error_threshold = 0.8
    reprojection_error_frames_markers = np.array(
        [
            [0.1, 0.2, 0.3],  # Mean reprojection error = 0.2
            [0.4, 0.5, 0.6],  # Mean reprojection error = 0.5
            [0.7, 0.8, 0.9],  # Mean reprojection error = 0.8
        ]
    )
    expected_output = []  # No frame has reprojection error above 0.8
    assert (
        find_frames_with_reprojection_error_above_limit(
            reprojection_error_threshold,
            reprojection_error_frames_markers,
        )
        == expected_output
    ), "Test failed with threshold equal to highest reprojection error"

    # test reprojection error threshold is 0
    reprojection_error_threshold = 0
    reprojection_error_frames_markers = np.array(
        [
            [0.1, 0.2, 0.3],  # Mean reprojection error = 0.2
            [0.4, 0.5, 0.6],  # Mean reprojection error = 0.5
            [0.7, 0.8, 0.9],  # Mean reprojection error = 0.8
        ]
    )
    expected_output = [0, 1, 2]  # All frames have reprojection error above 0
    assert (
        find_frames_with_reprojection_error_above_limit(
            reprojection_error_threshold,
            reprojection_error_frames_markers,
        )
        == expected_output
    ), "Test failed with 0 threshold"

    # test reprojection error threshold is negative
    reprojection_error_threshold = -0.5
    reprojection_error_frames_markers = np.array(
        [
            [0.1, 0.2, 0.3],  # Mean reprojection error = 0.2
            [0.4, 0.5, 0.6],  # Mean reprojection error = 0.5
            [0.7, 0.8, 0.9],  # Mean reprojection error = 0.8
        ]
    )
    expected_output = [0, 1, 2]  # All frames have reprojection error above -0.5
    assert (
        find_frames_with_reprojection_error_above_limit(
            reprojection_error_threshold,
            reprojection_error_frames_markers,
        )
        == expected_output
    ), "Test failed with negative threshold"

    # test reprojection error threshold is NaN
    reprojection_error_threshold = np.nan
    reprojection_error_frames_markers = np.array(
        [
            [0.1, 0.2, 0.3],  # Mean reprojection error = 0.2
            [0.4, 0.5, 0.6],  # Mean reprojection error = 0.5
            [0.7, 0.8, 0.9],  # Mean reprojection error = 0.8
        ]
    )
    expected_output = []  # No frame has reprojection error above NaN
    assert (
        find_frames_with_reprojection_error_above_limit(
            reprojection_error_threshold,
            reprojection_error_frames_markers,
        )
        == expected_output
    ), "Gave frames despite reprojection threshold being NaN"


def test_set_unincluded_data_to_nans():
    # test removing one camera
    mediapipe_2d_data = np.random.randint(0, 10, size=(3, 5, 1, 2)).astype(np.float32)
    frames_with_reprojection_error = [1, 3]
    cameras_to_remove = [0]
    data_to_reproject = set_unincluded_data_to_nans(
        mediapipe_2d_data=mediapipe_2d_data,
        frames_with_reprojection_error=frames_with_reprojection_error,
        cameras_to_remove=cameras_to_remove,
    )
    assert data_to_reproject.shape == (3, 2, 1, 2), "Changed shape of input array beyond removing frames"
    assert np.all(np.isnan(data_to_reproject[0, :, :, :])), "Did not NaN values from chosen camera"
    assert np.array_equal(data_to_reproject[1, :, :, :], np.take(mediapipe_2d_data, frames_with_reprojection_error, axis=1)[1, :, :, :]), "Changed values from camera that shouldn't be changed"
    assert np.array_equal(data_to_reproject[2, :, :, :], np.take(mediapipe_2d_data, frames_with_reprojection_error, axis=1)[2, :, :, :]), "Changed values from camera that shouldn't be changed"

    # test removing two cameras
    mediapipe_2d_data = np.random.randint(0, 10, size=(4, 7, 3, 2)).astype(np.float32)
    frames_with_reprojection_error = [1, 3, 6]
    cameras_to_remove = [1, 3]
    data_to_reproject = set_unincluded_data_to_nans(
        mediapipe_2d_data=mediapipe_2d_data,
        frames_with_reprojection_error=frames_with_reprojection_error,
        cameras_to_remove=cameras_to_remove,
    )
    assert data_to_reproject.shape == (4, 3, 3, 2), "Changed shape of input array beyond removing frames"
    assert np.all(np.isnan(data_to_reproject[1, :, :, :])), "Did not NaN values from chosen camera"
    assert np.all(np.isnan(data_to_reproject[3, :, :, :])), "Did not NaN values from chosen camera"
    assert np.array_equal(data_to_reproject[0, :, :, :], np.take(mediapipe_2d_data, frames_with_reprojection_error, axis=1)[0, :, :, :]), "Changed values from camera that shouldn't be changed"
    assert np.array_equal(data_to_reproject[2, :, :, :], np.take(mediapipe_2d_data, frames_with_reprojection_error, axis=1)[2, :, :, :]), "Changed values from camera that shouldn't be changed"
