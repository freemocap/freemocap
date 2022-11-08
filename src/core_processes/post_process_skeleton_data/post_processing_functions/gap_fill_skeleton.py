
import numpy as np
import pandas as pd
from rich.progress import track


def interpolate_freemocap_data(freemocap_marker_data:np.ndarray) -> np.ndarray:
    """ Takes in a 3d skeleton numpy array from freemocap and gap fills missing NaN values"""
    num_frames = freemocap_marker_data.shape[0]
    num_markers = freemocap_marker_data.shape[1]

    freemocap_interpolated_data = np.empty((num_frames, num_markers, 3))

    for marker in track(range(num_markers), description='Interpolating Data'):
        this_marker_skel3d_data = freemocap_marker_data[:, marker, :]
        df = pd.DataFrame(this_marker_skel3d_data)
        df2 = df.interpolate(method='linear', axis=0)  # use pandas interpolation methods to fill in missing data
        this_marker_interpolated_skel3d_array = np.array(df2)
        # replace the remaining NaN values (the ones that often happen at the start of the recording)
        this_marker_interpolated_skel3d_array = np.where(np.isfinite(this_marker_interpolated_skel3d_array),
                                                         this_marker_interpolated_skel3d_array,
                                                         np.nanmean(this_marker_interpolated_skel3d_array)
                                                         )

        freemocap_interpolated_data[:, marker, :] = this_marker_interpolated_skel3d_array

    return freemocap_interpolated_data


