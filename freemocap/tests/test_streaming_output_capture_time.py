import numpy as np
import pytest
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE
from freemocap.core.pipeline.realtime.temporal_pipeline import capture_timestamp
from freemocap.core.streaming.outputs.capture_time import camera_capture_timestamp_ns


def frame(before, after):
    value = np.zeros(1, dtype=np.dtype([("frame_metadata", FRAME_METADATA_DTYPE)])).view(np.recarray)
    value.frame_metadata.timestamps.pre_frame_grab_ns = before
    value.frame_metadata.timestamps.post_frame_grab_ns = after
    return value


def test_original_integer_midpoint_and_existing_filter_seconds_are_distinct_representations():
    source = frame(1_000_000_001, 1_000_000_004)
    original = source.copy()
    assert camera_capture_timestamp_ns(source) == 1_000_000_002  # Cam CSV's integer midpoint.
    assert capture_timestamp(source) == 1.0000000025  # Existing filter semantics unchanged.
    np.testing.assert_array_equal(source, original)


def test_original_nanoseconds_never_round_trip_through_float_seconds():
    source = frame(9_007_199_254_740_993, 9_007_199_254_740_997)
    assert camera_capture_timestamp_ns(source) == 9_007_199_254_740_995


@pytest.mark.parametrize("before,after", [(0, 1), (20, 10)])
def test_missing_or_invalid_capture_time_is_rejected(before, after):
    with pytest.raises(ValueError):
        camera_capture_timestamp_ns(frame(before, after))
