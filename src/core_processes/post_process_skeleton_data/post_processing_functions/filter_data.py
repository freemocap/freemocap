import numpy as np
from scipy import signal


def butterworth_lowpass_zerolag_filter(data, cutoff, sampling_rate, order):
    """Run a low pass butterworth filter on a single column of data"""
    nyquist_freq = 0.5 * sampling_rate
    normal_cutoff = cutoff / nyquist_freq
    # Get the filter coefficients
    b, a = signal.butter(order, normal_cutoff, btype="low", analog=False)
    y = signal.filtfilt(b, a, data)
    return y


def butterworth_filter_skeleton(skeleton_3d_data, cutoff, sampling_rate, order):
    """Take in a 3d skeleton numpy array and calculate_center_of_mass a low pass butterworth filter on each marker in
    the data"""
    number_of_frames = skeleton_3d_data.shape[0]
    number_of_markers = skeleton_3d_data.shape[1]
    butterworth_filtered_data = np.empty((number_of_frames, number_of_markers, 3))

    for marker_number in range(number_of_markers):
        for dimension in range(3):
            butterworth_filtered_data[
                :, marker_number, dimension
            ] = butterworth_lowpass_zerolag_filter(
                skeleton_3d_data[:, marker_number, dimension],
                cutoff,
                sampling_rate,
                order,
            )

    assert skeleton_3d_data.shape == butterworth_filtered_data.shape

    return butterworth_filtered_data
