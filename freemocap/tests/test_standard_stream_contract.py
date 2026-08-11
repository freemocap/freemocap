"""WS-1 — standard-stream wire contract (schema + sample + codecs).

Pure contract tests: schema/sample round-trips, size locks (the TS decoder in
WS-4 mirrors these), quaternion ``wxyz`` order, NaN-missing rows, per-camera
``OVERLAY_2D`` blocks, and schema→LSL flatten parity. No pipeline / WebSocket
wiring is exercised.
"""
import numpy as np
import pytest

from freemocap.core.streaming.standard_stream import (
    BLOCK_HEADER_SIZE,
    FREEMOCAP_CANONICAL_CONVENTION,
    SAMPLE_FOOTER_SIZE,
    SAMPLE_HEADER_SIZE,
    ChannelGroup,
    ChannelKind,
    MessageType,
    SampleBlock,
    StreamSample,
    StreamSchema,
    decode_sample,
    decode_schema,
    encode_sample,
    encode_schema,
    sample_to_flat_vector,
    schema_to_streaminfo_channels,
)


def _example_schema() -> StreamSchema:
    return StreamSchema(
        stream_id="stream-uuid-1234",
        stream_name="freemocap standard stream",
        coordinate_convention=FREEMOCAP_CANONICAL_CONVENTION,
        channels=(
            ChannelGroup(
                kind=ChannelKind.POINTS,
                names=("left_elbow", "right_elbow"),
                columns=("x", "y", "z", "reprojection_error"),
                units="mm",
            ),
            ChannelGroup(
                kind=ChannelKind.ROTATIONS,
                names=("left_upper_arm",),
                columns=("w", "x", "y", "z"),
                units="quaternion",
            ),
        ),
        connections=(("left_shoulder", "left_elbow"),),
        joint_hierarchy={"left_shoulder": ("left_elbow",)},
    )


def _example_sample() -> StreamSample:
    points = np.array(
        [
            [1.0, 2.0, 3.0, 0.5],
            [np.nan, np.nan, np.nan, np.nan],  # missing landmark → NaN row
        ],
        dtype=np.float32,
    )
    rotations = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)  # wxyz identity
    overlay_cam0 = np.array([[10.0, 20.0, 1.0], [30.0, 40.0, 0.0]], dtype=np.float32)
    overlay_cam1 = np.array([[11.0, 21.0, 1.0], [31.0, 41.0, 0.9]], dtype=np.float32)
    return StreamSample(
        timestamp=123.456,
        frame_number=42,
        subject_id=0,
        blocks=[
            SampleBlock(ChannelKind.POINTS, points),
            SampleBlock(ChannelKind.ROTATIONS, rotations),
            SampleBlock(ChannelKind.OVERLAY_2D, overlay_cam0, camera_id="cam-0"),
            SampleBlock(ChannelKind.OVERLAY_2D, overlay_cam1, camera_id="cam-1"),
        ],
    )


# --- header sizes (locked; the WS-4 TS decoder mirrors these) ---

def test_header_sizes_are_locked():
    assert SAMPLE_HEADER_SIZE == 32
    assert BLOCK_HEADER_SIZE == 28
    assert SAMPLE_FOOTER_SIZE == 32


# --- schema ---

def test_schema_roundtrip():
    schema = _example_schema()
    restored = decode_schema(encode_schema(schema))
    assert restored == schema
    assert restored.coordinate_convention == FREEMOCAP_CANONICAL_CONVENTION
    assert restored.channels[0].kind == ChannelKind.POINTS
    assert restored.joint_hierarchy["left_shoulder"] == ("left_elbow",)


# --- sample ---

def test_sample_roundtrip_preserves_nan_wxyz_and_camera_ids():
    sample = _example_sample()
    restored = decode_sample(encode_sample(sample))

    assert restored.timestamp == pytest.approx(123.456)
    assert restored.frame_number == 42
    assert restored.subject_id == 0
    assert len(restored.blocks) == 4

    # POINTS incl. the NaN-missing row (assert_array_equal treats NaN==NaN as equal)
    np.testing.assert_array_equal(restored.blocks[0].data, sample.blocks[0].data)
    # ROTATIONS wxyz order preserved
    assert restored.blocks[1].kind == ChannelKind.ROTATIONS
    np.testing.assert_array_equal(restored.blocks[1].data, sample.blocks[1].data)
    # OVERLAY_2D per-camera blocks keyed by camera_id
    assert restored.blocks[2].camera_id == "cam-0"
    assert restored.blocks[3].camera_id == "cam-1"
    np.testing.assert_array_equal(restored.blocks[2].data, sample.blocks[2].data)


def test_encode_is_deterministic():
    sample = _example_sample()
    assert encode_sample(sample) == encode_sample(sample)


def test_first_byte_demuxes_cleanly():
    blob = encode_sample(_example_sample())
    # byte 0 must avoid skellycam image (0/1/2) and legacy keypoints (3/4/5)
    assert blob[0] == int(MessageType.SAMPLE_HEADER)
    assert blob[0] not in (0, 1, 2, 3, 4, 5)


def test_decode_rejects_trailing_bytes():
    blob = encode_sample(_example_sample())
    with pytest.raises(ValueError):
        decode_sample(blob + b"\x00")


# --- LSL pass-through parity ---

def test_schema_and_sample_flatten_to_matching_lengths():
    schema = _example_schema()  # points(2×4) + rotations(1×4) = 12 channels
    channels = schema_to_streaminfo_channels(schema)
    assert len(channels) == 2 * 4 + 1 * 4
    assert channels[0] == ("left_elbow.x", "mm")

    sample = StreamSample(
        timestamp=0.0,
        frame_number=0,
        subject_id=0,
        blocks=[
            SampleBlock(ChannelKind.POINTS, np.zeros((2, 4), dtype=np.float32)),
            SampleBlock(ChannelKind.ROTATIONS, np.zeros((1, 4), dtype=np.float32)),
        ],
    )
    assert sample_to_flat_vector(sample).shape[0] == len(channels)


def test_flat_vector_includes_all_blocks():
    # Nothing excluded: points(2×4) + rotations(1×4) + 2 cameras × overlay(2×3) = 8 + 4 + 12 = 24.
    sample = _example_sample()
    assert sample_to_flat_vector(sample).shape[0] == 24
