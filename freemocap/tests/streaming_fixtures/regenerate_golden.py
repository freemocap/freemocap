"""Regenerate the F2a golden fixtures (schema JSON + one sample's bytes).

Run from ``project/freemocap``::

    uv run python -m freemocap.tests.streaming_fixtures.regenerate_golden

The fixtures are the F3 cross-language parity anchors: the TS decoder must
decode ``schema_golden.json`` and ``sample_golden.bin`` to the same values the
Python encoder produced here. They are built from a **synthetic** aggregator
message with pinned constants — do not change those constants without
re-running this script and the F3 parity check.

**Re-running this script REWRITES the pinned golden fixtures, and therefore IS
a wire-format/contract change** — a binary diff in ``sample_golden.bin`` is a
wire change. Re-run only with that intent, and re-check the F3 parity tests
after.

See ``freemocap/tests/test_stream_sample_encoder.py`` for the decoder-side
assertions that consume these fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from freemocap.core.streaming.standard_stream import StreamSample, StreamSchema, encode_sample, encode_schema
from freemocap.core.streaming.standard_stream.producers import compose, compose_sample
from freemocap.core.streaming.standard_stream.producers.producer_contexts import (
    FrameContext,
    StreamContext,
)
from freemocap.core.tasks.mocap.center_of_mass import CoMConfidence, CenterOfMassResult
from freemocap.core.tasks.mocap.tracker_mappings import tracker_keypoint_names
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage, CameraNodeOutputMessage
from skellyforge.data_models.trajectory_3d import Point3d
from skellyforge.skellymodels.standard_human.standard_human_model import compose_standard_human
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation

FIXTURE_DIR = Path(__file__).parent


def _observation(*, frame_number: int, body_points: dict[str, tuple[float, float]]) -> Observation:
    names = tuple(body_points.keys())
    xyz = np.array([(x, y, 0.0) for x, y in body_points.values()], dtype=np.float64)
    visibility = np.full(len(names), 1.0)
    kp = Keypoints(names=names, xyz=xyz, visibility=visibility)
    return Observation(
        frame_number=frame_number,
        image_size=(480, 640),
        stages={"body": StageObservation(name="body", keypoints=kp)},
    )


def build() -> tuple[StreamSchema, StreamSample]:
    model = compose_standard_human()
    context = StreamContext(
        standard_human=model,
        camera_ids=("cam-0", "cam-1"),
        # image_size is (height, width); the schema field is (width, height).
        camera_image_sizes={"cam-0": (640, 480), "cam-1": (640, 480)},
        tracker_keypoint_names=tracker_keypoint_names("rtmpose"),
        pipeline_live=True,
    )
    schema = compose(
        context,
        stream_id="golden-stream-id",
        stream_name="golden-standard-stream",
    ).schema

    standard_skeleton = {
        "hips_center": np.array([0.0, 0.0, 900.0]),
        "head_center": np.array([0.0, 0.0, 1600.0]),
        "left_shoulder": np.array([-250.0, 0.0, 1400.0]),
        "right_shoulder": np.array([250.0, 0.0, 1400.0]),
        "left_wrist": np.array([-300.0, 100.0, 1100.0]),
        "right_wrist": np.array([300.0, 100.0, 1100.0]),
        "left_index_finger_tip": np.array([-310.0, 120.0, 1050.0]),
    }
    rotation_world = {
        "hips": np.array([1.0, 0.0, 0.0, 0.0]),
        "spine": np.array([0.7071, 0.0, 0.0, 0.7071]),
        "left_upper_arm": np.array([0.0, 1.0, 0.0, 0.0]),
    }
    rotation_local = {
        "hips": np.array([1.0, 0.0, 0.0, 0.0]),
        "spine": np.array([0.0, 0.0, 0.0, 1.0]),
    }
    com = CenterOfMassResult(
        total_body_com=np.array([5.0, -3.0, 950.0]),
        segment_coms={},
        directly_observed_mass=1.0,
        confidence=CoMConfidence.high,
    )
    message = AggregationNodeOutputMessage(
        frame_number=42,
        pipeline_config=RealtimePipelineConfig(),
        camera_group_id="cg-0",
        camera_node_outputs={
            "cam-0": CameraNodeOutputMessage(
                camera_id="cam-0",
                frame_number=42,
                skeleton_observation=_observation(
                    frame_number=42,
                    body_points={
                        "nose": (320.0, 240.0),
                        "left_shoulder": (100.0, 200.0),
                        "right_shoulder": (500.0, 200.0),
                    },
                ),
            ),
            "cam-1": CameraNodeOutputMessage(
                camera_id="cam-1",
                frame_number=42,
                skeleton_observation=_observation(
                    frame_number=42,
                    body_points={"nose": (310.0, 250.0)},
                ),
            ),
        },
        center_of_mass_result=com,
        xcom=Point3d(x=12.5, y=-4.0, z=0.0),
        keypoints_arrays={
            "nose": np.array([0.0, 0.0, 1600.0]),
            "left_shoulder": np.array([-250.0, 0.0, 1400.0]),
            "right_shoulder": np.array([250.0, 0.0, 1400.0]),
            "left_wrist": np.array([-300.0, 100.0, 1100.0]),
        },
        standard_skeleton=standard_skeleton,
        segment_rotations_world=rotation_world,
        segment_rotations_local=rotation_local,
    )
    frame_ctx = FrameContext(
        frame_number=message.frame_number,
        timestamp=123.456,
        aggregator_output=message,
        # An odd-length fake JPEG pins the uint8 alignment path (the block is
        # composed last).
        image_payload=bytes([0xFF, 0xD8, 0xFF]) + b"golden-fake-jpeg",
    )
    sample = compose_sample(
        compose(
            context,
            stream_id="golden-stream-id",
            stream_name="golden-standard-stream",
        ),
        frame_ctx,
    )
    return schema, sample


def main() -> None:
    schema, sample = build()
    schema_bytes = encode_schema(schema)
    sample_bytes = encode_sample(sample)

    schema_path = FIXTURE_DIR / "schema_golden.json"
    sample_path = FIXTURE_DIR / "sample_golden.bin"

    schema_path.write_bytes(schema_bytes)
    sample_path.write_bytes(sample_bytes)
    print(f"wrote {schema_path} ({len(schema_bytes)} bytes)")
    print(f"wrote {sample_path} ({len(sample_bytes)} bytes)")


if __name__ == "__main__":
    main()
