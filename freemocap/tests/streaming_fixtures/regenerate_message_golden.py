"""Regenerate the message-model golden fixtures (CBOR bytes).

Run from project/freemocap::

    uv run python -m freemocap.tests.streaming_fixtures.regenerate_message_golden

These fixtures are the step-1 cross-language parity anchors: the TS codec must
decode each .bin to the same values this script pinned (freemocap-ui
.../message-golden.test.ts). They are built from synthetic pinned values — do
not change them without re-running this script and the TS parity check.

Re-running REWRITES the fixtures, and therefore IS a contract change.
"""
from __future__ import annotations

from pathlib import Path

from freemocap.core.streaming.message_model import (
    ChannelBlock,
    ChannelKind,
    ConventionMessage,
    FrameMessage,
    ModelMessage,
    Subject,
    encode_message,
)

FIXTURE_DIR = Path(__file__).parent


def build_convention_message() -> bytes:
    return encode_message(ConventionMessage())


def build_model_message() -> bytes:
    # A synthetic 2-segment model; the spine orientation is a non-exact unit
    # quaternion (90 deg about z) — it pins "no float16 downcast" on scalar
    # floats in the TS parity test.
    model = ModelMessage(
        segments=("hips", "spine"),
        orientations={
            "hips": (1.0, 0.0, 0.0, 0.0),
            "spine": (0.7071067811865476, 0.0, 0.0, 0.7071067811865476),
        },
        axes={"hips": "y", "spine": "y"},
        lengths={"hips": 100.0, "spine": 200.0},
        connections=(("hips", "spine"),),
        hierarchy={"hips": ("spine",), "spine": ()},
        parents={"hips": None, "spine": "hips"},
        rest_positions={"hips": (0.0, 0.0, 0.0), "spine": (0.0, 0.0, 100.0)},
    )
    return encode_message(model)


def build_frame_message() -> bytes:
    segment_origins = ChannelBlock.from_float32_rows(
        kind=ChannelKind.SEGMENT_ORIGINS,
        names=("hips", "spine"),
        columns=("x", "y", "z"),
        rows=[[0.0, 0.0, 0.0], [0.0, 0.0, 100.0]],
    )
    rotations_world = ChannelBlock.from_float32_rows(
        kind=ChannelKind.ROTATIONS_WORLD,
        names=("hips", "spine"),
        columns=("w", "x", "y", "z"),
        rows=[[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
    )
    frame = FrameMessage(
        frame_number=99,
        timestamp=1.5,
        subjects=(Subject(subject_id=0, channels=(segment_origins, rotations_world)),),
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
