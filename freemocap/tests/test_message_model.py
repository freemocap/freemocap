"""The message model: dataclasses + CBOR encode round-trip."""
from __future__ import annotations

import cbor2

from freemocap.core.streaming.message_model import (
    ChannelBlock,
    ChannelKind,
    CoordinateConvention,
    FrameMessage,
    MessageEnvelope,
    ModelInstance,
    encode_message,
)


def test_channel_block_packs_float32_little_endian():
    block = ChannelBlock.from_float32_rows(
        kind=ChannelKind.SEGMENT_ORIGINS,
        columns=("x", "y", "z"),
        rows=[[0.0, 0.0, 0.0], [0.0, 0.0, 100.0]],
    )
    assert block.kind == ChannelKind.SEGMENT_ORIGINS
    assert block.names is None  # index-keyed against the model's segments
    assert block.columns == ("x", "y", "z")
    assert len(block.data) == 6 * 4  # 2 rows x 3 columns x 4 bytes


def test_channel_block_carries_inline_names_for_tracker_keypoints():
    block = ChannelBlock.from_float32_rows(
        kind=ChannelKind.KEYPOINTS_3D,
        columns=("x", "y", "z", "reprojection_error"),
        rows=[[0.0, 0.0, 0.0, 0.5]],
        names=("nose",),
    )
    assert block.names == ("nose",)


def test_frame_message_round_trips_cbor():
    block = ChannelBlock.from_float32_rows(
        kind=ChannelKind.SEGMENT_ORIGINS,
        columns=("x", "y", "z"),
        rows=[[0.0, 0.0, 100.0]],
    )
    frame = FrameMessage(
        envelope=MessageEnvelope(timestamp=1.5),
        frame_number=99,
        instances=(ModelInstance(instance_id=0, model_id="standard_human", channels=(block,)),),
        image=b"\xff\xd8\xff",
    )
    decoded = cbor2.loads(encode_message(frame))
    assert decoded["kind"] == "frame"
    assert decoded["timestamp"] == 1.5
    assert decoded["frame_number"] == 99
    assert decoded["instances"][0]["instance_id"] == 0
    assert decoded["instances"][0]["channels"][0]["kind"] == "SEGMENT_ORIGINS"
    assert decoded["image"] == b"\xff\xd8\xff"


def test_coordinate_convention_defaults_to_freemocap_convention():
    message = CoordinateConvention()
    assert message.units.value == "mm"
    assert message.handedness.value == "right"
    assert message.up_axis.value == "+z"
    assert message.forward_axis.value == "+x"
    assert message.rotation_frame.value == "local"
    assert message.rotation_form.value == "quaternion"
