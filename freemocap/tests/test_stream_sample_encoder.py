"""F2a — the producer-composed sample + golden bytes.

The encoder half of F2 (doc 11 §4 Step 1 + Step 4). Builds one six-block sample
from a synthetic ``AggregationNodeOutputMessage`` + the F1 schema, asserts the
block kinds/dims + exact numbers, verifies the binary round-trip is field-exact, and
pins golden fixtures (schema JSON + one sample's bytes) as the F3 cross-language
parity anchors.

Golden fixture regeneration::

    uv run python -m freemocap.tests.streaming_fixtures.regenerate_golden

which rewrites ``schema_golden.json`` and ``sample_golden.bin``. The TS decoder
(F3) must decode these to the same values.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from freemocap.core.streaming.standard_stream import (
    ChannelKind,
    StreamSample,
    decode_sample,
    decode_schema,
    encode_sample,
    encode_schema,
)
from freemocap.core.streaming.standard_stream.producers import (
    compose,
    compose_sample,
)
from freemocap.core.streaming.standard_stream.producers.producer_contexts import (
    FrameContext,
    StreamContext,
)
from freemocap.core.tasks.mocap.center_of_mass import (
    CoMConfidence,
    CenterOfMassResult,
)
from freemocap.core.tasks.mocap.tracker_mappings import tracker_keypoint_names
from freemocap.core.pipeline.realtime.realtime_pipeline_config import (
    RealtimePipelineConfig,
)
from freemocap.pubsub.pubsub_topics import (
    AggregationNodeOutputMessage,
    CameraNodeOutputMessage,
)
from skellyforge.data_models.trajectory_3d import Point3d
from skellyforge.skellymodels.standard_human.standard_human_model import (
    compose_standard_human,
)
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation


FIXTURE_DIR = Path(__file__).parent / "streaming_fixtures"


def _model():
    return compose_standard_human()


def _schema(**kwargs):
    """The composed schema for the synthetic two-camera rtmpose stream."""
    kw = dict(
        standard_human=_model(),
        camera_ids=("cam-0", "cam-1"),
        tracker_keypoint_names=tracker_keypoint_names("rtmpose"),
        pipeline_live=True,
    )
    kw.update(kwargs)
    return compose(
        StreamContext(**kw),
        stream_id="golden-stream-id",
        stream_name="golden-standard-stream",
    ).schema


def _sample(message=None, *, timestamp=None, image_payload=None) -> StreamSample:
    """Compose one sample from the synthetic message through the producers."""
    if message is None:
        message = _message()
    frame_ctx = FrameContext(
        frame_number=message.frame_number,
        timestamp=timestamp if timestamp is not None else 0.0,
        aggregator_output=message,
        image_payload=image_payload,
    )
    composition = compose(
        StreamContext(
            standard_human=_model(),
            camera_ids=("cam-0", "cam-1"),
            tracker_keypoint_names=tracker_keypoint_names("rtmpose"),
            pipeline_live=True,
        ),
        stream_id="golden-stream-id",
        stream_name="golden-standard-stream",
    )
    return compose_sample(composition, frame_ctx)


def _observation(*, frame_number: int, body_points: dict[str, tuple[float, float]]) -> Observation:
    """A minimal per-camera skeleton Observation with a ``body`` stage."""
    names = tuple(body_points.keys())
    xyz = np.array([(x, y, 0.0) for x, y in body_points.values()], dtype=np.float64)
    visibility = np.full(len(names), 1.0)
    kp = Keypoints(names=names, xyz=xyz, visibility=visibility)
    return Observation(
        frame_number=frame_number,
        image_size=(480, 640),
        stages={"body": StageObservation(name="body", keypoints=kp)},
    )


def _message(**kwargs) -> AggregationNodeOutputMessage:
    """A synthetic aggregator output with known values.

    standard_skeleton carries standard-human-named positions (the rigidified
    solver input): a known body point, a known hand point, and a known hand tip.
    """
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
        "hips": np.array([1.0, 0.0, 0.0, 0.0]),       # identity
        "spine": np.array([0.7071, 0.0, 0.0, 0.7071]),  # +Z ~90°
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
    kw_defaults = dict(
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
        keypoints_arrays={
            "nose": np.array([0.0, 0.0, 1600.0]),
            "left_shoulder": np.array([-250.0, 0.0, 1400.0]),
            "right_shoulder": np.array([250.0, 0.0, 1400.0]),
            "left_wrist": np.array([-300.0, 100.0, 1100.0]),
        },
        center_of_mass_result=com,
        xcom=Point3d(x=12.5, y=-4.0, z=0.0),
        skeleton=None,
        standard_skeleton=standard_skeleton,
        segment_rotations_world=rotation_world,
        segment_rotations_local=rotation_local,
    )
    kw_defaults.update(kwargs)
    return AggregationNodeOutputMessage(**kw_defaults)


# ── block construction ────────────────────────────────────────────────


def _block_by_kind(sample: StreamSample, kind: ChannelKind) -> list:
    return [b for b in sample.blocks if b.kind is kind]


def test_sample_has_groups_in_producer_order():
    sample = _sample(image_payload=b"jpeg")
    kinds = [b.kind for b in sample.blocks]
    # 10 groups in producer order; the overlay kinds are one per camera (2) →
    # 12 blocks; IMAGE_JPEG composes last (odd-length uint8 blob must not
    # precede float32).
    assert kinds == [
        ChannelKind.KEYPOINTS_3D,
        ChannelKind.LANDMARKS_3D,
        ChannelKind.SEGMENT_ORIGINS,
        ChannelKind.ROTATIONS_LOCAL,
        ChannelKind.ROTATIONS_WORLD,
        ChannelKind.SEGMENT_LENGTHS,
        ChannelKind.OVERLAY_2D,
        ChannelKind.OVERLAY_REPROJECTIONS,
        ChannelKind.OVERLAY_2D,
        ChannelKind.OVERLAY_REPROJECTIONS,
        ChannelKind.DERIVED_POINTS,
        ChannelKind.IMAGE_JPEG,
    ]


def test_keypoints_3d_dims_and_values():
    sample = _sample()
    (kp,) = _block_by_kind(sample, ChannelKind.KEYPOINTS_3D)
    group = _schema().channels[0]
    assert kp.data.shape == (len(group.names), 4)  # tracker keypoints × (x,y,z,reprojection_error)

    # positions keyed by tracker name, from message.keypoints_arrays
    name_to_idx = {n: i for i, n in enumerate(group.names)}
    nose_row = kp.data[name_to_idx["nose"]]
    np.testing.assert_array_equal(nose_row[:3], np.array([0.0, 0.0, 1600.0], dtype=np.float32))
    assert np.isnan(nose_row[3])  # reprojection_error not carried this task

    # a tracker keypoint with no observation this frame → full NaN row
    missing = "left_ankle"
    assert missing in name_to_idx
    assert np.all(np.isnan(kp.data[name_to_idx[missing]]))


def test_landmarks_3d_dims_and_values():
    sample = _sample()
    (lm,) = _block_by_kind(sample, ChannelKind.LANDMARKS_3D)
    group = _schema().channels[1]
    assert lm.data.shape == (76, 4)  # landmarks × (x,y,z,reprojection_error)
    assert len(group.names) == 76

    # positions keyed by standard-human name, from message.standard_skeleton
    name_to_idx = {n: i for i, n in enumerate(group.names)}
    hips_row = lm.data[name_to_idx["hips_center"]]
    np.testing.assert_array_equal(hips_row[:3], np.array([0.0, 0.0, 900.0], dtype=np.float32))
    assert np.isnan(hips_row[3])

    # a missing landmark → full NaN row
    missing = "left_big_toe"
    assert missing in name_to_idx
    assert np.all(np.isnan(lm.data[name_to_idx[missing]]))


def test_segment_origins_from_origin_landmark():
    sample = _sample()
    (orig,) = _block_by_kind(sample, ChannelKind.SEGMENT_ORIGINS)
    group = _schema().channels[2]
    assert orig.data.shape == (60, 3)
    name_to_idx = {n: i for i, n in enumerate(group.names)}
    # left_upper_arm's origin == left_shoulder
    np.testing.assert_array_equal(
        orig.data[name_to_idx["left_upper_arm"]],
        np.array([-250.0, 0.0, 1400.0], dtype=np.float32),
    )
    # hips origin == hips_center
    np.testing.assert_array_equal(
        orig.data[name_to_idx["hips"]],
        np.array([0.0, 0.0, 900.0], dtype=np.float32),
    )
    # a segment whose origin keypoint is absent → NaN row (e.g. left_knee not supplied)
    assert np.all(np.isnan(orig.data[name_to_idx["left_lower_leg"]]))


def test_rotations_wxyz_match_message():
    sample = _sample()
    world = _block_by_kind(sample, ChannelKind.ROTATIONS_WORLD)[0]
    local = _block_by_kind(sample, ChannelKind.ROTATIONS_LOCAL)[0]
    group = _schema().channels[3]
    assert world.data.shape == (60, 4)
    name_to_idx = {n: i for i, n in enumerate(group.names)}

    np.testing.assert_array_equal(
        world.data[name_to_idx["hips"]],
        np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
    )
    np.testing.assert_allclose(
        world.data[name_to_idx["spine"]],
        np.array([0.7071, 0.0, 0.0, 0.7071], dtype=np.float32),
    )
    # unsolved segment → NaN wxyz
    assert np.all(np.isnan(world.data[name_to_idx["head"]]))

    np.testing.assert_array_equal(
        local.data[name_to_idx["spine"]],
        np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
    )


def test_derived_points_com_and_xcom():
    sample = _sample()
    (derived,) = _block_by_kind(sample, ChannelKind.DERIVED_POINTS)
    group = _schema().channels[8]
    names = group.names  # ("center_of_mass", "xcom")
    name_to_idx = {n: i for i, n in enumerate(names)}
    assert derived.data.shape == (2, 3)
    np.testing.assert_array_equal(
        derived.data[name_to_idx["center_of_mass"]],
        np.array([5.0, -3.0, 950.0], dtype=np.float32),
    )
    np.testing.assert_array_equal(
        derived.data[name_to_idx["xcom"]],
        np.array([12.5, -4.0, 0.0], dtype=np.float32),
    )


def test_xcom_none_yields_nan_row():
    sample = _sample(message=_message(xcom=None))
    (derived,) = _block_by_kind(sample, ChannelKind.DERIVED_POINTS)
    names = _schema().channels[8].names
    name_to_idx = {n: i for i, n in enumerate(names)}
    assert np.all(np.isnan(derived.data[name_to_idx["xcom"]]))


def test_overlay_2d_detections_per_camera():
    sample = _sample()
    overlays = _block_by_kind(sample, ChannelKind.OVERLAY_2D)
    assert len(overlays) == 2  # one per camera

    by_cam = {o.camera_id: o for o in overlays}
    assert set(by_cam) == {"cam-0", "cam-1"}

    kp_group = _schema().channels[0]
    name_to_idx = {n: i for i, n in enumerate(kp_group.names)}

    cam0 = by_cam["cam-0"].data
    assert cam0.shape == (len(kp_group.names), 3)  # tracker keypoints × (x,y,visibility)
    np.testing.assert_array_equal(
        cam0[name_to_idx["nose"], :2],
        np.array([320.0, 240.0], dtype=np.float32),
    )
    # the tracker's confidence rides the visibility column
    assert cam0[name_to_idx["nose"], 2] == 1.0
    # a keypoint not seen by this camera → NaN
    assert np.all(np.isnan(cam0[name_to_idx["left_wrist"]]))


def test_segment_lengths_block_carries_measured_values():
    sample = _sample(message=_message(segment_lengths={"hips": 246.5, "spine": 263.5}))
    (lengths,) = _block_by_kind(sample, ChannelKind.SEGMENT_LENGTHS)
    group = _schema().channels[5]
    assert lengths.data.shape == (60, 1)
    name_to_idx = {n: i for i, n in enumerate(group.names)}
    assert lengths.data[name_to_idx["hips"]][0] == pytest.approx(246.5)
    assert lengths.data[name_to_idx["spine"]][0] == pytest.approx(263.5)
    # unmeasured segment → NaN row
    assert np.isnan(lengths.data[name_to_idx["head"]][0])


def test_image_jpeg_block_carries_raw_bytes():
    jpeg = bytes([0xFF, 0xD8, 0xFF]) + b"fake-jpeg"  # odd length — pins the uint8 alignment path
    sample = _sample(image_payload=jpeg)
    (image,) = _block_by_kind(sample, ChannelKind.IMAGE_JPEG)
    assert image.data.dtype == np.uint8
    assert image.data.tobytes() == jpeg


def test_no_image_payload_omits_the_block():
    """A frame with no image payload (e.g. shm eviction) ships no image block;
    the consumer keeps its last image."""
    sample = _sample(image_payload=None)
    assert _block_by_kind(sample, ChannelKind.IMAGE_JPEG) == []


def test_overlay_reprojections_per_camera():
    sample = _sample(message=_message(reprojected_segment_origins={
        "cam-0": {"hips": (320.0, 240.0), "spine": (310.0, 230.0)},
        "cam-1": {"hips": (310.0, 250.0)},
    }))
    reprojs = _block_by_kind(sample, ChannelKind.OVERLAY_REPROJECTIONS)
    assert len(reprojs) == 2  # one per camera

    by_cam = {r.camera_id: r for r in reprojs}
    assert set(by_cam) == {"cam-0", "cam-1"}

    group = _schema().channels[7]
    name_to_idx = {n: i for i, n in enumerate(group.names)}
    cam0 = by_cam["cam-0"].data
    assert cam0.shape == (60, 3)  # segment names × (x,y,visibility)
    np.testing.assert_array_equal(
        cam0[name_to_idx["hips"], :2],
        np.array([320.0, 240.0], dtype=np.float32),
    )
    # a segment with no reprojection this frame → NaN row
    assert np.all(np.isnan(cam0[name_to_idx["head"]]))


# ── round-trip ─────────────────────────────────────────────────────────


def test_sample_roundtrip_field_by_field():
    sample = _sample(timestamp=123.456)
    restored = StreamSample.from_bytes(sample.to_bytes())

    assert restored.timestamp == pytest.approx(123.456)
    assert restored.frame_number == 42
    assert restored.subject_id == 0
    assert len(restored.blocks) == len(sample.blocks)
    for orig, dec in zip(sample.blocks, restored.blocks):
        assert orig.kind is dec.kind
        assert orig.camera_id == dec.camera_id
        np.testing.assert_array_equal(orig.data, dec.data)


def test_encode_is_deterministic_via_method():
    sample = _sample()
    assert sample.to_bytes() == sample.to_bytes()


# ── golden fixtures ────────────────────────────────────────────────────


def test_golden_schema_roundtrip():
    golden = FIXTURE_DIR / "schema_golden.json"
    assert golden.exists(), "golden fixtures missing — run the regeneration command"
    schema = decode_schema(golden.read_bytes())
    # the golden schema is a canonical compose_standard_human()-derived schema
    assert schema.stream_id == "golden-stream-id"
    assert [g.kind for g in schema.channels] == [
        ChannelKind.KEYPOINTS_3D,
        ChannelKind.LANDMARKS_3D,
        ChannelKind.SEGMENT_ORIGINS,
        ChannelKind.ROTATIONS_LOCAL,
        ChannelKind.ROTATIONS_WORLD,
        ChannelKind.SEGMENT_LENGTHS,
        ChannelKind.OVERLAY_2D,
        ChannelKind.OVERLAY_REPROJECTIONS,
        ChannelKind.DERIVED_POINTS,
        ChannelKind.IMAGE_JPEG,
    ]
    # the real rtmpose tracker keypoint set, sorted
    assert schema.channels[0].names == tracker_keypoint_names("rtmpose")
    assert schema.channels[1].names[0] == "head_center"  # sorted landmarks first


def test_golden_sample_decodes_to_pinned_values():
    golden = FIXTURE_DIR / "sample_golden.bin"
    assert golden.exists(), "golden fixtures missing — run the regeneration command"
    sample = decode_sample(golden.read_bytes())

    assert sample.frame_number == 42
    lm = _block_by_kind(sample, ChannelKind.LANDMARKS_3D)[0]
    group = _schema().channels[1]
    name_to_idx = {n: i for i, n in enumerate(group.names)}
    np.testing.assert_array_equal(
        lm.data[name_to_idx["hips_center"], :3],
        np.array([0.0, 0.0, 900.0], dtype=np.float32),
    )

    world = _block_by_kind(sample, ChannelKind.ROTATIONS_WORLD)[0]
    seg_to_idx = {n: i for i, n in enumerate(_schema().channels[3].names)}
    np.testing.assert_allclose(
        world.data[seg_to_idx["spine"]],
        np.array([0.7071, 0.0, 0.0, 0.7071], dtype=np.float32),
    )
