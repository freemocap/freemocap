"""Carry SkellyCam's recorded acquisition midpoint without a float round trip."""
import numpy as np
from skellycam.core.timestamps.numpy_timestamps.calculate_timestamps_numpy import (
    calculate_frame_grab_timestamps,
)


def camera_capture_timestamp_ns(frame: np.recarray) -> int:
    stamps = frame.frame_metadata.timestamps
    before = int(stamps.pre_frame_grab_ns[0])
    after = int(stamps.post_frame_grab_ns[0])
    if before <= 0 or after < before:
        raise ValueError("Capture bounds must be positive and ordered")
    return int(calculate_frame_grab_timestamps(stamps.reshape(1, 1))[0, 0])
