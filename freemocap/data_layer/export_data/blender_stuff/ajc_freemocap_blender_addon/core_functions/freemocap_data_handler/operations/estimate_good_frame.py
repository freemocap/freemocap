import logging
from typing import Dict

import numpy as np

logger = logging.getLogger(__name__)


def estimate_good_frame(trajectories_with_error: Dict[str, Dict[str, np.ndarray]], ignore_first_n_frames: int = 30):
    names = list(trajectories_with_error.keys())
    all_good_frames = None

    for name in names:
        velocities = np.diff(trajectories_with_error[name]['trajectory'], axis=0)
        velocities = np.insert(velocities, 0, np.nan, axis=0)
        velocities_mag = np.sqrt(np.sum(velocities ** 2, axis=1))
        velocities = np.nan_to_num(velocities, nan=np.inf)

        errors = trajectories_with_error[name]['error']

        # define threshold for 'standing still'
        velocity_threshold = np.nanpercentile(velocities_mag, 10)

        # Get the indices of the good frames
        good_frames_indices = np.where((velocities_mag <= velocity_threshold) & (~np.isnan(errors)))[0]

        # If no good frames found, skip this trajectory
        if good_frames_indices.size == 0:
            continue

        # intersect good_frames_indices with all_good_frames
        if all_good_frames is None:
            all_good_frames = set(good_frames_indices)
        else:
            all_good_frames = all_good_frames.intersection(set(good_frames_indices))

    # If no good frames found in any trajectory, raise an Exception
    if not all_good_frames:
        raise Exception("No good frames found! Please check your data.")

    # Convert the set back to a numpy array
    all_good_frames = np.array(list(all_good_frames))

    # Get the velocities of the good frames
    good_frames_velocities = velocities_mag[all_good_frames]

    # Find the index of the good frame with the lowest velocity
    best_frame = all_good_frames[np.argmin(good_frames_velocities)]

    return best_frame
