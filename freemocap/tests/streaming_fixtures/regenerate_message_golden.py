"""Regenerate the message-model golden fixtures (CBOR bytes).

Run from project/freemocap::

    uv run python -m freemocap.tests.streaming_fixtures.regenerate_message_golden

These fixtures are the cross-language parity anchors: the TS codec must decode
each .bin to the same values this script pinned (freemocap-ui
.../message-golden.test.ts). They are built from synthetic pinned values — do
not change them without re-running this script and the TS parity check.

Re-running REWRITES the fixtures, and therefore IS a contract change.
"""
from __future__ import annotations

from pathlib import Path

import cbor2

from freemocap.core.streaming.message_model import (
    ChannelBlock,
    ChannelKind,
    CoordinateConvention,
    FrameMessage,
    MessageEnvelope,
    ModelDefinition,
    ModelInstance,
    encode_message,
)
from freemocap.core.streaming.rest_geometry import (
    PrimaryAxis,
    RestLandmark,
    RestSegment,
)

FIXTURE_DIR = Path(__file__).parent


def build_convention_message() -> bytes:
    return cbor2.dumps(CoordinateConvention().to_cbor_message())


def build_model_message() -> bytes:
    # A synthetic 2-segment model; the spine orientation is a non-exact unit
    # quaternion (90 deg about z) — it pins "no float16 downcast" on scalar
    # floats in the TS parity test.
    model = ModelDefinition(
        model_id="standard_human",
        segments=(
            RestSegment(
                name="hips",
                parent=None,
                primary_axis=PrimaryAxis(value="y"),
                rest_orientation=(1.0, 0.0, 0.0, 0.0),
                length_mm=100.0,
            ),
            RestSegment(
                name="spine",
                parent="hips",
                primary_axis=PrimaryAxis(value="y"),
                rest_orientation=(0.7071067811865476, 0.0, 0.0, 0.7071067811865476),
                length_mm=200.0,
            ),
        ),
        landmarks=(
            RestLandmark(name="hips_center", rest_position=(0.0, 0.0, 0.0)),
            RestLandmark(name="neck_center", rest_position=(0.0, 0.0, 200.0)),
        ),
    )
    return cbor2.dumps(model.to_cbor_message())


def build_frame_message() -> bytes:
    segment_origins = ChannelBlock.from_float32_rows(
        kind=ChannelKind.SEGMENT_ORIGINS,
        columns=("x", "y", "z"),
        rows=[[0.0, 0.0, 0.0], [0.0, 0.0, 100.0]],
    )
    rotations_world = ChannelBlock.from_float32_rows(
        kind=ChannelKind.ROTATIONS_WORLD,
        columns=("w", "x", "y", "z"),
        rows=[[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
    )
    frame = FrameMessage(
        envelope=MessageEnvelope(timestamp=1.5),
        frame_number=99,
        instances=(
            ModelInstance(instance_id=0, model_id="standard_human", channels=(segment_origins, rotations_world)),
        ),
        image=b"\xff\xd8\xffgolden-fake-jpeg",
    )
    return encode_message(frame)


MESSAGES = {
    "message_convention_golden.bin": build_convention_message,
    "message_model_golden.bin": build_model_message,
    "message_frame_golden.bin": build_frame_message,
}


def main() -> None:
    for filename, builder in MESSAGES.items():
        data = builder()
        path = FIXTURE_DIR / filename
        path.write_bytes(data)
        print("wrote %s (%d bytes)" % (path, len(data)))


if __name__ == "__main__":
    main()
