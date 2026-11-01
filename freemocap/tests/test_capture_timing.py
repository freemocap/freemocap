import numpy as np
import pytest
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE
from freemocap.core.tracking.capture_timing import tracker_capture_timestamp_ms


def frame(before, after):
    record = np.zeros(1, dtype=np.dtype([('frame_metadata', FRAME_METADATA_DTYPE)])).view(np.recarray)
    record.frame_metadata.timestamps.pre_frame_grab_ns = before
    record.frame_metadata.timestamps.post_frame_grab_ns = after
    return record


def test_inference_time_uses_capture_midpoints_and_retains_skipped_frame_duration():
    records = [frame(1_000_000_000, 1_002_000_000), frame(1_002_000_000, 1_004_000_000)]
    assert tracker_capture_timestamp_ms(records) == 1002
    for record in records:
        record.frame_metadata.frame_number = 9999  # Scheduling identity is not elapsed time.
    assert tracker_capture_timestamp_ms(records) == 1002
    later = [frame(1_100_000_000, 1_102_000_000), frame(1_102_000_000, 1_104_000_000)]
    assert tracker_capture_timestamp_ms(later) - tracker_capture_timestamp_ms(records) == 100


def test_invalid_capture_timing_is_rejected():
    with pytest.raises(ValueError): tracker_capture_timestamp_ms([])
    with pytest.raises(ValueError): tracker_capture_timestamp_ms([frame(20, 10)])
