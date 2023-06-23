from scipy import signal
import numpy as np
from rich.progress import track

def butter_lowpass_filter(data, cutoff, sampling_rate, order):
    """ Run a low pass butterworth filter on a single column of data"""
    nyquist_freq = 0.5*sampling_rate
    normal_cutoff = cutoff / nyquist_freq
    # Get the filter coefficients 
    b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
    y = signal.filtfilt(b, a, data)
    return y


def filter_skeleton_data(skeleton_3d_data, order, cutoff, sampling_rate):
    """ Take in a 3d skeleton numpy array and run a low pass butterworth filter on each marker in the data"""
    num_frames = skeleton_3d_data.shape[0]
    num_markers = skeleton_3d_data.shape[1]
    filtered_data = np.empty((num_frames,num_markers,3))

    for marker in track(range(num_markers), description = 'Filtering Data'):
        for x in range(3):
            filtered_data[:,marker,x] = butter_lowpass_filter(skeleton_3d_data[:,marker,x],cutoff,sampling_rate,order)

    
    return filtered_data
