import numpy as np
import pandas as pd


class CharucoVisibilityError(RuntimeError):
    """Raised when no frame satisfies the ‘all-corners-visible & stationary’ criteria."""


class CharucoVelocityError(RuntimeError):
    """Raised when the velocity of the ChArUco corners is too high to be considered stationary."""


def get_charuco_x_and_y_idx(number_of_squares_width: int, number_of_squares_height: int):
    """
    For a given board definition, get the corner marker indexes needed to make the x and y vectors
    """

    num_cols = number_of_squares_width - 1  # corner columns
    num_rows = number_of_squares_height - 1  # corner rows

    idx_x = num_cols * (num_rows - 1)
    idx_y = num_cols - 1

    return idx_x, idx_y


def get_unit_vector(vector: np.ndarray) -> np.ndarray:
    return vector / np.linalg.norm(vector)


def compute_basis_vectors_of_new_reference(
        charuco_frame: np.ndarray, number_of_squares_width: int, number_of_squares_height: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    origin = charuco_frame[0]

    idx_x, idx_y = get_charuco_x_and_y_idx(
        number_of_squares_width=number_of_squares_width, number_of_squares_height=number_of_squares_height
    )

    x_vec = charuco_frame[idx_x] - origin
    y_vec = charuco_frame[idx_y] - origin

    x_hat = get_unit_vector(x_vec)
    y_hat_raw = get_unit_vector(y_vec)
    z_hat = get_unit_vector(np.cross(x_hat, y_hat_raw))
    y_hat = get_unit_vector(np.cross(z_hat, x_hat))

    return x_hat, y_hat, z_hat


def find_still_frame(points_velocity: np.ndarray, max_allowed_velocity: float = 1.0) -> int:
    visible_frames = ~np.isnan(points_velocity).any(axis=1)
    if not np.any(visible_frames):
        raise CharucoVisibilityError(
            "No frame found where all three required ChArUco corners are on the ground and visible."
        )

    max_velocity_per_frame = np.nanmax(points_velocity[visible_frames], axis=1)
    if np.nanmin(max_velocity_per_frame) > max_allowed_velocity:
        raise CharucoVelocityError(
            f"All frames have ChArUco corner velocity > {max_allowed_velocity:.2f} mm/s — check that the board is stationary."
        )

    best_visible_index = int(np.nanargmin(max_velocity_per_frame))
    best_velocity_index = np.where(visible_frames)[0][
        best_visible_index
    ]  # maps back to the original array (which we sliced earlier to get rid of rows with nans)
    return best_velocity_index


def find_good_frame(
        charuco_data3d_fr_id_xyz: np.ndarray,
        number_of_squares_width: int,
        number_of_squares_height: int,
        frame_to_use: int = 0,
        search_range: int = 120,
):
    if frame_to_use == 0:
        slice_to_search = slice(0, search_range)
    elif frame_to_use == -1:
        slice_to_search = slice(-search_range, None)
    elif frame_to_use > 0:
        start_frame = max(0, frame_to_use - search_range)
        end_frame = min(charuco_data3d_fr_id_xyz.shape[0], frame_to_use + search_range)
        slice_to_search = slice(start_frame, end_frame)
    else:
        raise ValueError(f"Invalid value for frame_to_use: {frame_to_use}")

    idx_x, idx_y = get_charuco_x_and_y_idx(
        number_of_squares_width=number_of_squares_width, number_of_squares_height=number_of_squares_height
    )

    charuco_corners = charuco_data3d_fr_id_xyz[slice_to_search, [0, idx_y, idx_x]]
    charuco_corners_velocity = np.linalg.norm(np.diff(charuco_corners, axis=0), axis=2)
    best_velocity_frame = find_still_frame(points_velocity=charuco_corners_velocity)

    frame_offset = slice_to_search.start or 0
    best_position_frame = best_velocity_frame + frame_offset + 1
    return best_position_frame


def interpolate_skeleton_data(skeleton_data: np.ndarray, method_to_use='linear', order=3) -> np.ndarray:
    """ Takes in a 3d skeleton numpy array from freemocap and interpolates missing NaN values"""
    num_frames = skeleton_data.shape[0]
    num_markers = skeleton_data.shape[1]

    freemocap_interpolated_data = np.empty((num_frames, num_markers, 3))

    for marker in range(num_markers):
        this_marker_skel3d_data = skeleton_data[:, marker, :]
        df = pd.DataFrame(this_marker_skel3d_data)
        df2 = df.interpolate(method=method_to_use, axis=0,
                             order=order)  # use pandas interpolation methods to fill in missing data
        # df.interpolate(method=method_to_use, order = 5)
        this_marker_interpolated_skel3d_array = np.array(df2)
        # replace the remaining NaN values (the ones that often happen at the start of the recording)
        this_marker_interpolated_skel3d_array = np.where(np.isfinite(this_marker_interpolated_skel3d_array),
                                                         this_marker_interpolated_skel3d_array,
                                                         np.nanmean(this_marker_interpolated_skel3d_array))

        freemocap_interpolated_data[:, marker, :] = this_marker_interpolated_skel3d_array

    return freemocap_interpolated_data


def skellyforge_data(raw_charuco_data: np.ndarray):
    interpolated_data = interpolate_skeleton_data(
        skeleton_data=raw_charuco_data
    )
    return interpolated_data
