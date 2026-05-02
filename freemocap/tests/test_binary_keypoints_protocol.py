"""Round-trip tests for the binary keypoints websocket message.

The wire format is parsed by the freemocap-ui frontend; this test stands in
for that parser by reading the same dtypes back out with numpy and asserting
the bytes survive the trip unchanged.
"""
import numpy as np
import pytest

from freemocap.api.websocket.binary_keypoints_protocol import (
    BLOCK_HEADER_SIZE,
    BlockKind,
    Dtype,
    KEYPOINTS_BLOCK_HEADER_DTYPE,
    KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE,
    MessageType,
    PAYLOAD_FOOTER_SIZE,
    PAYLOAD_HEADER_SIZE,
    numpy_dtype_for,
)
from freemocap.core.viz.frontend_keypoints_serializer import build_keypoints_payload


POINT_NAMES = ("nose", "left_shoulder", "right_shoulder", "left_hip", "right_hip")


def test_dtype_sizes_are_stable():
    # Frontend mirrors these sizes — flag any change so the TS side is updated
    # in the same commit.
    assert PAYLOAD_HEADER_SIZE == 24
    assert PAYLOAD_FOOTER_SIZE == 24
    assert BLOCK_HEADER_SIZE == 60


def test_round_trip_3d_blocks():
    raw = {
        "nose": np.array([1.0, 2.0, 3.0], dtype=np.float64),
        "left_shoulder": np.array([10.0, 20.0, 30.0], dtype=np.float64),
        # right_shoulder intentionally missing → NaN row + visibility 0
        "left_hip": np.array([100.0, 200.0, 300.0], dtype=np.float64),
        "right_hip": np.array([1000.0, 2000.0, 3000.0], dtype=np.float64),
    }
    filtered = {
        # Subset only — filtered points are typically a subset of raw
        "nose": np.array([1.1, 2.1, 3.1], dtype=np.float64),
    }

    blob = build_keypoints_payload(
        frame_number=42,
        tracker_id="rtmpose_wholebody",
        point_names=POINT_NAMES,
        keypoints_raw_arrays=raw,
        keypoints_filtered_arrays=filtered,
    )

    expected_block_size = BLOCK_HEADER_SIZE + len(POINT_NAMES) * 4 * 4  # f32, 4 cols
    expected_total = PAYLOAD_HEADER_SIZE + 2 * expected_block_size + PAYLOAD_FOOTER_SIZE
    assert len(blob) == expected_total

    buf = bytes(blob)

    header = np.frombuffer(buf[:PAYLOAD_HEADER_SIZE], dtype=KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE)[0]
    assert int(header["message_type"]) == int(MessageType.KEYPOINTS_PAYLOAD_HEADER)
    assert int(header["frame_number"]) == 42
    assert int(header["num_blocks"]) == 2

    cursor = PAYLOAD_HEADER_SIZE
    for kind, sparse in [
        (BlockKind.KEYPOINTS_RAW_3D, raw),
        (BlockKind.KEYPOINTS_FILTERED_3D, filtered),
    ]:
        block_header = np.frombuffer(
            buf[cursor:cursor + BLOCK_HEADER_SIZE],
            dtype=KEYPOINTS_BLOCK_HEADER_DTYPE,
        )[0]
        assert int(block_header["message_type"]) == int(MessageType.KEYPOINTS_BLOCK_HEADER)
        assert int(block_header["block_kind"]) == int(kind)
        assert int(block_header["dtype_code"]) == int(Dtype.FLOAT32)
        assert int(block_header["dims"]) == 3
        assert block_header["tracker_id"].decode("ascii").rstrip("\x00") == "rtmpose_wholebody"
        assert block_header["camera_id"].decode("ascii").rstrip("\x00") == ""
        assert int(block_header["num_points"]) == len(POINT_NAMES)
        cursor += BLOCK_HEADER_SIZE

        wire_dtype = numpy_dtype_for(Dtype.FLOAT32)
        data_len = int(block_header["data_byte_length"])
        assert data_len == len(POINT_NAMES) * 4 * wire_dtype.itemsize
        flat = np.frombuffer(buf[cursor:cursor + data_len], dtype=wire_dtype)
        arr = flat.reshape(len(POINT_NAMES), 4)
        cursor += data_len

        for i, name in enumerate(POINT_NAMES):
            if name in sparse:
                expected = sparse[name].astype(np.float32)
                np.testing.assert_array_equal(arr[i, :3], expected)
                assert arr[i, 3] == 1.0
            else:
                assert np.all(np.isnan(arr[i, :3]))
                assert arr[i, 3] == 0.0

    footer = np.frombuffer(buf[cursor:cursor + PAYLOAD_FOOTER_SIZE], dtype=KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE)[0]
    assert int(footer["message_type"]) == int(MessageType.KEYPOINTS_PAYLOAD_FOOTER)
    assert int(footer["frame_number"]) == 42
    assert int(footer["num_blocks"]) == 2
    cursor += PAYLOAD_FOOTER_SIZE
    assert cursor == len(blob)


def test_empty_dicts_produce_all_nan_rows():
    blob = build_keypoints_payload(
        frame_number=0,
        tracker_id="rtmpose_wholebody",
        point_names=POINT_NAMES,
        keypoints_raw_arrays={},
        keypoints_filtered_arrays={},
    )
    # First block payload starts at PAYLOAD_HEADER_SIZE + BLOCK_HEADER_SIZE
    start = PAYLOAD_HEADER_SIZE + BLOCK_HEADER_SIZE
    end = start + len(POINT_NAMES) * 4 * 4
    arr = np.frombuffer(bytes(blob)[start:end], dtype=np.float32).reshape(len(POINT_NAMES), 4)
    assert np.all(np.isnan(arr[:, :3]))
    assert np.all(arr[:, 3] == 0.0)


def test_first_byte_is_payload_header_message_type():
    # The frontend demuxes inbound binary frames on byte 0. Image frames use
    # MessageType.PAYLOAD_HEADER = 0; keypoints messages must use a distinct
    # value or the demux fails.
    blob = build_keypoints_payload(
        frame_number=1,
        tracker_id="rtmpose_wholebody",
        point_names=POINT_NAMES,
        keypoints_raw_arrays={},
        keypoints_filtered_arrays={},
    )
    assert blob[0] == int(MessageType.KEYPOINTS_PAYLOAD_HEADER)
    assert int(MessageType.KEYPOINTS_PAYLOAD_HEADER) >= 3  # avoids skellycam image protocol values 0/1/2


def test_tracker_id_truncates_safely_on_overlong_input():
    # Defensive: if a tracker ever has a name >16 chars, we should still emit
    # a valid blob (truncated id), not crash.
    blob = build_keypoints_payload(
        frame_number=0,
        tracker_id="x" * 64,
        point_names=POINT_NAMES,
        keypoints_raw_arrays={},
        keypoints_filtered_arrays={},
    )
    block_header = np.frombuffer(
        bytes(blob)[PAYLOAD_HEADER_SIZE:PAYLOAD_HEADER_SIZE + BLOCK_HEADER_SIZE],
        dtype=KEYPOINTS_BLOCK_HEADER_DTYPE,
    )[0]
    assert block_header["tracker_id"] == b"x" * 32
