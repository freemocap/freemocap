"""Adapt SkellyCam capture timestamps to Tracker's millisecond context."""
from collections.abc import Sequence
import numpy as np


def tracker_capture_timestamp_ms(frame_records: Sequence[np.recarray]) -> int:
    """Mean capture midpoint for the camera frames entering this inference batch.

    Use the same pre/post-grab midpoint convention as recorded camera timing.
    Keep integer nanoseconds until the final conversion required by Tracker and
    MediaPipe; processing delay and frame ordinals do not determine elapsed time.
    """
    if not frame_records:
        raise ValueError('Capture timing requires at least one frame')
    total_ns = 0
    for record in frame_records:
        timestamps = record.frame_metadata.timestamps
        before = int(timestamps.pre_frame_grab_ns[0])
        after = int(timestamps.post_frame_grab_ns[0])
        if before < 0 or after < before:
            raise ValueError('Invalid pre/post-grab capture timestamps')
        total_ns += before + after
    return total_ns // (2_000_000 * len(frame_records))
