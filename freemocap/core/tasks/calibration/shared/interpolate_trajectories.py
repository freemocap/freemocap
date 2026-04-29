import numpy as np
import scipy.interpolate


def interpolate_trajectory_data(
        trajectory_data: np.ndarray,
        method_to_use: str = "linear",
        order: int = 3,
) -> np.ndarray:
    """Interpolate missing NaN values in a numpy array of shape (n_frames, n_markers, 3).

    Args:
        trajectory_data: (n_frames, n_markers, 3) array with possible NaN gaps.
        method_to_use: 'linear', 'polynomial', or 'cubic'.
        order: Polynomial order (only used when method_to_use='polynomial').

    Returns:
        Interpolated array of same shape with NaN gaps filled.
    """
    if trajectory_data.ndim != 3 or trajectory_data.shape[2] != 3:
        raise ValueError(f"Expected shape (n_frames, n_markers, 3), got {trajectory_data.shape}")

    if method_to_use not in ("linear", "polynomial", "cubic"):
        raise ValueError(
            f"Unknown interpolation method: {method_to_use!r}. Must be 'linear', 'polynomial', or 'cubic'.")

    n_frames, n_markers, n_dims = trajectory_data.shape
    interpolated = trajectory_data.copy()
    all_frames = np.arange(n_frames)

    for marker in range(n_markers):
        for dim in range(n_dims):
            series = trajectory_data[:, marker, dim]
            valid_mask = np.isfinite(series)

            if not np.any(valid_mask):
                raise ValueError(f"Marker {marker} dim {dim} is entirely NaN — cannot interpolate.")

            if np.all(valid_mask):
                continue

            valid_frames = all_frames[valid_mask]
            valid_values = series[valid_mask]
            nan_frames = all_frames[~valid_mask]

            if method_to_use == "linear":
                # np.interp clamps to edge values for out-of-bounds frames
                interpolated[nan_frames, marker, dim] = np.interp(nan_frames, valid_frames, valid_values)

            elif method_to_use == "polynomial":
                interp_fn = scipy.interpolate.interp1d(
                    valid_frames,
                    valid_values,
                    kind=order,
                    bounds_error=False,
                    fill_value=(valid_values[0], valid_values[-1]),
                )
                interpolated[nan_frames, marker, dim] = interp_fn(nan_frames)

            elif method_to_use == "cubic":
                interp_fn = scipy.interpolate.CubicSpline(valid_frames, valid_values, extrapolate=False)
                result = interp_fn(nan_frames)
                result[nan_frames < valid_frames[0]] = valid_values[0]
                result[nan_frames > valid_frames[-1]] = valid_values[-1]
                interpolated[nan_frames, marker, dim] = result

    return interpolated
