"""The message model: dataclasses + CBOR encode round-trip."""
from __future__ import annotations

import cbor2

from freemocap.core.streaming.message_model import (
    ChannelBlock,
    ChannelKind,
    ConventionMessage,
    FrameMessage,
    Subject,
    encode_message,
)


def test_channel_block_packs_float32_little_endian():
    block = ChannelBlock.from_float32_rows(
        kind=ChannelKind.SEGMENT_ORIGINS,
        names=("hips", "spine"),
        columns=("x", "y", "z"),
        rows=[[0.0, 0.0, 0.0], [0.0, 0.0, 100.0]],
    )
    assert block.kind == ChannelKind.SEGMENT_ORIGINS
    assert block.names == ("hips", "spine")
    assert block.columns == ("x", "y", "z")
    assert len(block.data) == 6 * 4  # 2 rows x 3 columns x 4 bytes


def test_frame_message_round_trips_cbor():
    block = ChannelBlock.from_float32_rows(
        kind=ChannelKind.SEGMENT_ORIGINS,
        names=("hips",),
        columns=("x", "y", "z"),
        rows=[[0.0, 0.0, 100.0]],
    )
    frame = FrameMessage(
        frame_number=99,
        timestamp=1.5,
        subjects=(Subject(subject_id=0, channels=(block,)),),
        image=b"\xff\xd8\xff",
    )
    decoded = cbor2.loads(encode_message(frame))
    assert decoded["kind"] == "frame"
    assert decoded["frame_number"] == 99
    assert decoded["subjects"][0]["subject_id"] == 0
    assert decoded["subjects"][0]["channels"][0]["kind"] == "SEGMENT_ORIGINS"
    assert decoded["image"] == b"\xff\xd8\xff"


def test_convention_message_defaults_to_freemocap_convention():
    message = ConventionMessage()
    assert message.units.value == "mm"
    assert message.handedness.value == "right"
    assert message.up_axis.value == "+z"
    assert message.forward_axis.value == "+x"
    assert message.rotation_frame.value == "local"
    assert message.rotation_form.value == "quaternion"
