import numpy as np
import pandas as pd


def interpolate_trajectory_data(trajectory_data: np.ndarray, method_to_use: str = "linear", order: int = 3) -> np.ndarray:
    """Interpolate missing NaN values in a  numpy array of shape (n_frames, n_markers, 3) using pandas interpolation.

    Args:
        trajectory_data: (n_frames, n_markers, 3) array with possible NaN gaps.
        method_to_use: Pandas interpolation method (e.g. 'linear', 'polynomial').
        order: Order for polynomial/spline interpolation methods.

    Returns:
        Interpolated array with same shape, NaN gaps filled.
    """
    num_frames = trajectory_data.shape[0]
    num_markers = trajectory_data.shape[1]
    interpolated = np.empty((num_frames, num_markers, 3))

    for marker in range(num_markers):
        marker_data = trajectory_data[:, marker, :]
        df = pd.DataFrame(marker_data)
        df_interpolated = df.interpolate(method=method_to_use, axis=0, order=order)
        marker_array = np.array(df_interpolated)
        # Fill remaining NaNs (e.g. at recording start) with column mean
        marker_array = np.where(
            np.isfinite(marker_array),
            marker_array,
            np.nanmean(marker_array),
        )
        interpolated[:, marker, :] = marker_array

    return interpolated
