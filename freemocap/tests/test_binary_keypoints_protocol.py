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


def test_round_trip_3d_block():
    keypoints = {
        "nose": np.array([1.0, 2.0, 3.0], dtype=np.float64),
        "left_shoulder": np.array([10.0, 20.0, 30.0], dtype=np.float64),
        # right_shoulder intentionally missing → NaN row + visibility 0
        "left_hip": np.array([100.0, 200.0, 300.0], dtype=np.float64),
        "right_hip": np.array([1000.0, 2000.0, 3000.0], dtype=np.float64),
    }

    blob = build_keypoints_payload(
        frame_number=42,
        tracker_id="rtmpose_wholebody",
        point_names=POINT_NAMES,
        keypoints_arrays=keypoints,
    )

    expected_block_size = BLOCK_HEADER_SIZE + len(POINT_NAMES) * 4 * 4  # f32, 4 cols
    # Single block when no calibration points are present
    expected_total = PAYLOAD_HEADER_SIZE + expected_block_size + PAYLOAD_FOOTER_SIZE
    assert len(blob) == expected_total

    buf = bytes(blob)

    header = np.frombuffer(buf[:PAYLOAD_HEADER_SIZE], dtype=KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE)[0]
    assert int(header["message_type"]) == int(MessageType.KEYPOINTS_PAYLOAD_HEADER)
    assert int(header["frame_number"]) == 42
    assert int(header["num_blocks"]) == 1

    cursor = PAYLOAD_HEADER_SIZE

    block_header = np.frombuffer(
        buf[cursor:cursor + BLOCK_HEADER_SIZE],
        dtype=KEYPOINTS_BLOCK_HEADER_DTYPE,
    )[0]
    assert int(block_header["message_type"]) == int(MessageType.KEYPOINTS_BLOCK_HEADER)
    assert int(block_header["block_kind"]) == int(BlockKind.KEYPOINTS_3D)
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
        if name in keypoints:
            expected = keypoints[name].astype(np.float32)
            np.testing.assert_array_equal(arr[i, :3], expected)
            assert arr[i, 3] == 1.0
        else:
            assert np.all(np.isnan(arr[i, :3]))
            assert arr[i, 3] == 0.0

    footer = np.frombuffer(buf[cursor:cursor + PAYLOAD_FOOTER_SIZE], dtype=KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE)[0]
    assert int(footer["message_type"]) == int(MessageType.KEYPOINTS_PAYLOAD_FOOTER)
    assert int(footer["frame_number"]) == 42
    assert int(footer["num_blocks"]) == 1
    cursor += PAYLOAD_FOOTER_SIZE
    assert cursor == len(blob)


def test_empty_dict_produces_all_nan_rows():
    blob = build_keypoints_payload(
        frame_number=0,
        tracker_id="rtmpose_wholebody",
        point_names=POINT_NAMES,
        keypoints_arrays={},
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
        keypoints_arrays={},
    )
    assert blob[0] == int(MessageType.KEYPOINTS_PAYLOAD_HEADER)
    assert int(MessageType.KEYPOINTS_PAYLOAD_HEADER) >= 3  # avoids skellycam image protocol values 0/1/2


def test_skeleton_block_round_trip():
    # The FABRIK skeleton rides the binary path as a SKELETON_3D block with
    # embedded names (mixed canonical body + tracker hand naming).
    skeleton = {
        "left_shoulder": np.array([1.0, 2.0, 3.0], dtype=np.float64),
        "right_hand_thumb1": np.array([4.0, 5.0, 6.0], dtype=np.float64),
    }
    blob = build_keypoints_payload(
        frame_number=7,
        tracker_id="rtmpose_wholebody",
        point_names=POINT_NAMES,
        keypoints_arrays={},          # no keypoints/calib → schema block + skeleton block
        skeleton_arrays=skeleton,
    )
    buf = bytes(blob)

    header = np.frombuffer(buf[:PAYLOAD_HEADER_SIZE], dtype=KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE)[0]
    assert int(header["num_blocks"]) == 2  # keypoints (schema) + skeleton

    # Block 1: the (all-NaN) keypoints schema block — skip past it.
    cursor = PAYLOAD_HEADER_SIZE
    b1 = np.frombuffer(buf[cursor:cursor + BLOCK_HEADER_SIZE], dtype=KEYPOINTS_BLOCK_HEADER_DTYPE)[0]
    assert int(b1["block_kind"]) == int(BlockKind.KEYPOINTS_3D)
    cursor += BLOCK_HEADER_SIZE + int(b1["data_byte_length"])

    # Block 2: the skeleton block with embedded names.
    b2 = np.frombuffer(buf[cursor:cursor + BLOCK_HEADER_SIZE], dtype=KEYPOINTS_BLOCK_HEADER_DTYPE)[0]
    assert int(b2["block_kind"]) == int(BlockKind.SKELETON_3D)
    assert b2["tracker_id"].decode("ascii").rstrip("\x00") == "skeleton3d"
    assert int(b2["num_points"]) == 2
    cursor += BLOCK_HEADER_SIZE

    data = buf[cursor:cursor + int(b2["data_byte_length"])]
    # embed_names layout: [u4 names_len][names_blob \0-delimited][float32 data]
    names_len = int(np.frombuffer(data[:4], dtype="<u4")[0])
    names = [n for n in data[4:4 + names_len].decode("ascii").split("\x00") if n]
    assert names == ["left_shoulder", "right_hand_thumb1"]

    floats = np.frombuffer(
        data[4 + names_len:], dtype=numpy_dtype_for(Dtype.FLOAT32),
    ).reshape(2, 4)
    np.testing.assert_array_equal(floats[0, :3], np.array([1, 2, 3], dtype=np.float32))
    np.testing.assert_array_equal(floats[1, :3], np.array([4, 5, 6], dtype=np.float32))
    assert floats[0, 3] == 1.0 and floats[1, 3] == 1.0


def test_tracker_id_truncates_safely_on_overlong_input():
    # Defensive: if a tracker ever has a name >16 chars, we should still emit
    # a valid blob (truncated id), not crash.
    blob = build_keypoints_payload(
        frame_number=0,
        tracker_id="x" * 64,
        point_names=POINT_NAMES,
        keypoints_arrays={},
    )
    block_header = np.frombuffer(
        bytes(blob)[PAYLOAD_HEADER_SIZE:PAYLOAD_HEADER_SIZE + BLOCK_HEADER_SIZE],
        dtype=KEYPOINTS_BLOCK_HEADER_DTYPE,
    )[0]
    assert block_header["tracker_id"] == b"x" * 32
