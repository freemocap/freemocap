"""F5a — the full realtime loop, backend half of the gate (message path).

Synthetic rtmpose keypoints (Blender convention: +X right, +Y forward, +Z up) -> the
real tracker mapping -> hydrate_skeleton + ContinuousRollResolver -> a real aggregator
message -> a self-describing frame message -> CBOR -> the wire rotations equal the
solver's, and a standing run yields non-NaN ROTATIONS_WORLD for every hydrated segment.
An arm-abduction frame set then shows the change lands where it should: the humerus
rotates ~90° while the chest stays put.

This is the backend half of F5; the frontend integration test and the user's
manual run are the other halves.
"""
from __future__ import annotations

import math

import cbor2
import numpy as np

# NOTE the import order matters: realtime_pipeline_config must NOT be the first
# freemocap import — importing it first trips a circular import through
# pubsub_topics (pubsub_topics imports the config; if the config is still
# mid-init, the re-import finds it partially initialized).
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.message_model import encode_message
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext
from freemocap.core.tasks.mocap.tracker_mappings import (
    load_standard_human_mapping,
    tracker_keypoint_names,
)
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.hydration import hydrate_skeleton
from skellyforge.core.skeleton.pose.roll_resolution import ContinuousRollResolver
from skellyforge.core.skeleton.pose.rest_pose import RestPose
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition


def _standing_pose() -> dict[str, np.ndarray]:
    """A standing rtmpose-named pose in the Blender convention (+X right, +Y forward, +Z up).

    NOT the model's T-pose — proportions differ from the reference geometry, so
    the solved world quaternions are finite near-identity values, not exact
    identity (the exact identity-at-T-pose contract lives in skellyforge's own
    tests). The gate asks for a realistic stream that solves without NaN.
    """

    def p(x: float, y: float, z: float) -> np.ndarray:
        return np.array([float(x), float(y), float(z)])

    return {
        "nose": p(0, 0, 1720),
        "left_eye": p(-30, 0, 1730),
        "right_eye": p(30, 0, 1730),
        "left_ear": p(-60, 0, 1700),
        "right_ear": p(60, 0, 1700),
        "left_shoulder": p(-200, 0, 1450),
        "right_shoulder": p(200, 0, 1450),
        "left_elbow": p(-220, 0, 1150),
        "right_elbow": p(220, 0, 1150),
        "left_wrist": p(-230, 0, 900),
        "right_wrist": p(230, 0, 900),
        "left_hip": p(-120, 0, 950),
        "right_hip": p(120, 0, 950),
        "left_knee": p(-130, 0, 500),
        "right_knee": p(130, 0, 500),
        "left_ankle": p(-140, 0, 80),
        "right_ankle": p(140, 0, 80),
        "left_big_toe": p(-140, 150, 20),
        "right_big_toe": p(140, 150, 20),
        "left_small_toe": p(-160, 140, 20),
        "right_small_toe": p(160, 140, 20),
        "left_heel": p(-140, -40, 40),
        "right_heel": p(140, -40, 40),
    }


def _abducted_left_arm(pose: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """The standing pose with the left arm abducted 90° (elbow/wrist out to −X)."""
    out = {name: pos.copy() for name, pos in pose.items()}
    shoulder = pose["left_shoulder"]
    out["left_elbow"] = shoulder + np.array([-300.0, 0.0, 0.0])
    out["left_wrist"] = shoulder + np.array([-600.0, 0.0, 0.0])
    return out


def _hydrate(
    pose: dict[str, np.ndarray],
) -> tuple[SkeletonDefinition, RestPose, dict[str, np.ndarray], dict[str, np.ndarray]]:
    """The aggregator's exact per-frame reconstruction order, one frame.

    tracker mapping -> Point conversion -> hydrate_skeleton (partial) ->
    ContinuousRollResolver, then hydrate the segment origins onto the mapped
    landmarks (the wire's standard_skeleton).
    """
    skeleton = SkeletonDefinition.from_default_yaml()
    rest_pose = RestPose.from_default_yaml(skeleton=skeleton)
    resolver = ContinuousRollResolver.for_skeleton(skeleton=skeleton)
    mapping = load_standard_human_mapping("rtmpose")
    mapped = mapping(pose)
    observed = {name: Point.from_array(values=position) for name, position in mapped.items()}
    resolved = resolver.resolve_pose(
        pose=hydrate_skeleton(skeleton=skeleton, observed=observed, require_all=False)
    )
    hydrated_landmarks = dict(mapped)
    for segment in skeleton.segments.values():
        if segment.name in resolved.segment_poses:
            origin_name = segment.frame_definition.origin_point_name
            hydrated_landmarks[origin_name] = resolved.segment_poses[segment.name].origin.array
    world = {name: sp.orientation.as_array() for name, sp in resolved.segment_poses.items()}
    return skeleton, rest_pose, world, hydrated_landmarks


def _message(
    skeleton: SkeletonDefinition,
    world: dict[str, np.ndarray],
    hydrated_landmarks: dict[str, np.ndarray],
    pose: dict[str, np.ndarray],
) -> AggregationNodeOutputMessage:
    """A real aggregator message: tracker keypoints + hydrated landmarks + solved rotations."""
    return AggregationNodeOutputMessage(
        frame_number=7,
        pipeline_config=RealtimePipelineConfig(),
        camera_group_id="cg-0",
        camera_node_outputs={},
        keypoints_arrays=pose,
        total_body_com=np.zeros(3),
        xcom=np.zeros(3),
        skeleton=hydrated_landmarks,
        standard_skeleton=hydrated_landmarks,
        segment_rotations_world=world,
        segment_rotations_local={},
        segment_lengths={seg.name: seg.length for seg in skeleton.segments.values()},
    )


def _frame_message(
    skeleton: SkeletonDefinition,
    rest_pose: RestPose,
    world: dict[str, np.ndarray],
    hydrated_landmarks: dict[str, np.ndarray],
    pose: dict[str, np.ndarray],
) -> dict:
    """Compose the self-describing frame message, encode, and CBOR-decode."""
    composition = compose_messages(
        StreamContext(
            standard_human=skeleton,
            rest_pose=rest_pose,
            camera_ids=("cam-0", "cam-1"),
            tracker_keypoint_names=tracker_keypoint_names("rtmpose"),
            detector_type="rtmpose",
            pipeline_live=True,
        )
    )
    frame = composition.compose_frame_message(
        FrameContext(
            frame_number=7,
            timestamp=0.0,
            aggregator_output=_message(skeleton, world, hydrated_landmarks, pose),
        )
    )
    return cbor2.loads(encode_message(frame))


def _channel_by_kind(restored: dict, kind: str) -> dict:
    homes = [*restored.get("instances", ()), *restored.get("trackers", ())]
    for home in homes:
        for channel in home["channels"]:
            if channel["kind"] == kind:
                return channel
    raise AssertionError(f"no {kind} channel in the frame")


def _channel_data(channel: dict, cols: int) -> np.ndarray:
    # Segment/landmark channels are index-keyed (names dropped); the row count
    # is derivable from the packed float32 byte length alone.
    return np.frombuffer(channel["data"], dtype="<f4").reshape(-1, cols)


def _quat_angle_rad(a: np.ndarray, b: np.ndarray) -> float:
    """The rotation angle between two unit quaternions (shortest arc)."""
    dot = abs(float(np.dot(a, b)))
    return 2.0 * math.acos(min(1.0, dot))


# ── The gate ──────────────────────────────────────────────────────────────


def test_full_loop_wire_rotations_equal_solver_and_are_finite():
    """aggregator -> frame message -> CBOR -> decode: rotations identical + non-NaN."""
    pose = _standing_pose()
    skeleton, rest_pose, world, hydrated = _hydrate(pose)

    assert world, "the standing pose must hydrate segments"
    for name, q in world.items():
        assert np.all(np.isfinite(q)), f"ROTATIONS_WORLD non-finite for {name}"
        assert abs(float(np.linalg.norm(q)) - 1.0) < 1e-6, f"non-unit quaternion for {name}"

    restored = _frame_message(skeleton, rest_pose, world, hydrated, pose)

    # ROTATIONS_WORLD rows equal the solver's quaternions (float32 wire).
    world_channel = _channel_by_kind(restored, "ROTATIONS_WORLD")
    world_data = _channel_data(world_channel, 4)
    # ROTATIONS_WORLD is index-keyed against the model's segment order.
    name_to_idx = {n: i for i, n in enumerate(skeleton.segments)}
    for name, q in world.items():
        np.testing.assert_allclose(
            world_data[name_to_idx[name]], np.asarray(q, dtype=np.float32), atol=1e-6
        )

    # LANDMARKS_3D carries the hydrated pelvis_origin (the pelvis segment's origin).
    lm_channel = _channel_by_kind(restored, "LANDMARKS_3D")
    lm_data = _channel_data(lm_channel, 4)
    # LANDMARKS_3D is index-keyed against the model's landmark order.
    pelvis_idx = tuple(skeleton.landmarks).index("pelvis_origin")
    np.testing.assert_allclose(
        lm_data[pelvis_idx, :3], hydrated["pelvis_origin"], atol=1e-4
    )

    # KEYPOINTS_3D carries the tracker-named nose measurement.
    kp_channel = _channel_by_kind(restored, "KEYPOINTS_3D")
    kp_data = _channel_data(kp_channel, 4)
    nose_idx = kp_channel["names"].index("nose")
    np.testing.assert_allclose(kp_data[nose_idx, :3], pose["nose"], atol=1e-4)


def test_arm_abduction_rotates_humerus_and_leaves_spine():
    """The change lands where it should: ~90° on the humerus, ~0° on the chest."""
    standing_world = _hydrate(_standing_pose())[2]
    bent_world = _hydrate(_abducted_left_arm(_standing_pose()))[2]

    standing_humerus = standing_world["left_upper_arm"]
    bent_humerus = bent_world["left_upper_arm"]
    angle = _quat_angle_rad(standing_humerus, bent_humerus)
    assert abs(angle - math.pi / 2) < 0.2, f"humerus rotated {math.degrees(angle):.1f}°, expected ~90°"

    standing_chest = standing_world["chest"]
    bent_chest = bent_world["chest"]
    assert _quat_angle_rad(standing_chest, bent_chest) < 0.1, "chest must not rotate with the arm"
