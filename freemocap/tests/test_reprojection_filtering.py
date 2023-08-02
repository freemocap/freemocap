import numpy as np

from freemocap.core_processes.capture_volume_calibration.reprojection_filtering import find_frames_with_reprojection_error_above_limit

def test_find_frames_with_reprojection_error_above_limit():
    # test reprojection error threshold is 0.5
    reprojection_error_threshold = 0.5
    reprojection_error_frames_markers = np.array([
        [0.1, 0.2, 0.3],  # Mean reprojection error = 0.2
        [0.4, 0.5, 0.6],  # Mean reprojection error = 0.5
        [0.7, 0.8, 0.9],  # Mean reprojection error = 0.8
    ])
    expected_output = [2]  # Only the third frame has reprojection error above 0.5
    assert find_frames_with_reprojection_error_above_limit(
        reprojection_error_threshold,
        reprojection_error_frames_markers,
    ) == expected_output, "Did not find correct frames with reprojection error above threshold"

    # test reprojection error threshold is 0.8
    reprojection_error_threshold = 0.8
    reprojection_error_frames_markers = np.array([
        [0.1, 0.2, 0.3],  # Mean reprojection error = 0.2
        [0.4, 0.5, 0.6],  # Mean reprojection error = 0.5
        [0.7, 0.8, 0.9],  # Mean reprojection error = 0.8
    ])
    expected_output = []  # No frame has reprojection error above 0.8
    assert find_frames_with_reprojection_error_above_limit(
        reprojection_error_threshold,
        reprojection_error_frames_markers,
    ) == expected_output, "Test failed with threshold equal to highest reprojection error"

    # test reprojection error threshold is 0
    reprojection_error_threshold = 0
    reprojection_error_frames_markers = np.array([
        [0.1, 0.2, 0.3],  # Mean reprojection error = 0.2
        [0.4, 0.5, 0.6],  # Mean reprojection error = 0.5
        [0.7, 0.8, 0.9],  # Mean reprojection error = 0.8
    ])
    expected_output = [0, 1, 2]  # All frames have reprojection error above 0
    assert find_frames_with_reprojection_error_above_limit(
        reprojection_error_threshold,
        reprojection_error_frames_markers,
    ) == expected_output, "Test failed with 0 threshold"

    # test reprojection error threshold is negative
    reprojection_error_threshold = -0.5
    reprojection_error_frames_markers = np.array([
        [0.1, 0.2, 0.3],  # Mean reprojection error = 0.2
        [0.4, 0.5, 0.6],  # Mean reprojection error = 0.5
        [0.7, 0.8, 0.9],  # Mean reprojection error = 0.8
    ])
    expected_output = [0, 1, 2]  # All frames have reprojection error above -0.5
    assert find_frames_with_reprojection_error_above_limit(
        reprojection_error_threshold,
        reprojection_error_frames_markers,
    ) == expected_output, "Test failed with negative threshold"

    # test reprojection error threshold is NaN
    reprojection_error_threshold = np.nan
    reprojection_error_frames_markers = np.array([
        [0.1, 0.2, 0.3],  # Mean reprojection error = 0.2
        [0.4, 0.5, 0.6],  # Mean reprojection error = 0.5
        [0.7, 0.8, 0.9],  # Mean reprojection error = 0.8
    ])
    expected_output = []  # No frame has reprojection error above NaN
    assert find_frames_with_reprojection_error_above_limit(
        reprojection_error_threshold,
        reprojection_error_frames_markers,
    ) == expected_output, "Gave frames despite reprojection threshold being NaN"