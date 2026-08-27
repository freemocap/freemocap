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
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
from freemocap.core.skeletons.standard_human_skeleton import (
    STANDARD_HUMAN_MODEL_ID,
    build_standard_human_bundle,
)
from freemocap.core.tasks.mocap.tracker_mappings import load_standard_human_mapping
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
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
    mapped = mapping.apply(tracker_positions=pose)
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
    """A real aggregator message: tracker keypoints + one skeleton's reconstruction."""
    return AggregationNodeOutputMessage(
        frame_number=7,
        pipeline_config=RealtimePipelineConfig(),
        camera_group_id="cg-0",
        camera_node_outputs={},
        keypoints_arrays=pose,
        reconstructions={
            STANDARD_HUMAN_MODEL_ID: SkeletonReconstruction(
                model_id=STANDARD_HUMAN_MODEL_ID,
                landmarks=hydrated_landmarks,
                segment_rotations_world=world,
                center_of_mass=np.zeros(3),
                extrapolated_center_of_mass=np.zeros(3),
                segment_lengths={
                    seg.name: seg.length for seg in skeleton.segments.values()
                },
                fitted_scale_mm=1700.0,
            )
        },
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
            skeletons=(
                build_standard_human_bundle(
                    detector_type="rtmpose", scale_window_frames=30
                ),
            ),
            camera_ids=("cam-0", "cam-1"),
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


def _segment_direction(
    skeleton: SkeletonDefinition, world: dict[str, np.ndarray], name: str
) -> np.ndarray:
    """Where a solved segment actually points: its local primary axis, rotated to world."""
    segment = skeleton.segments[name]
    local = segment.landmarks[segment.frame_definition.primary_point_name].local_position.array
    signed = float(segment.frame_definition.primary_axis.sign) * local
    signed = signed / float(np.linalg.norm(signed))
    rotation = RotationQuaternion.from_array(array=np.asarray(world[name], dtype=np.float64))
    return rotation.rotate_vector(vector=signed)


def test_arm_abduction_points_the_humerus_where_the_data_says_and_leaves_the_trunk():
    """The change lands where it should: the humerus follows the observed bone, trunk still.

    Asserted on the segment's DIRECTION rather than on the angle between two quaternions.
    Both are shortest-arc solutions about different axes and then have their roll supplied
    by convention, so the quaternion-to-quaternion angle is not the angle the arm moved
    through — it is convention plus motion. The direction is the part that is measured, and
    it is what "the humerus followed the arm" means.
    """
    standing_pose = _standing_pose()
    abducted_pose = _abducted_left_arm(standing_pose)
    skeleton, _, standing_world, _ = _hydrate(standing_pose)
    _, _, bent_world, _ = _hydrate(abducted_pose)

    for label, pose, world in (
        ("standing", standing_pose, standing_world),
        ("abducted", abducted_pose, bent_world),
    ):
        observed = pose["left_elbow"] - pose["left_shoulder"]
        observed = observed / np.linalg.norm(observed)
        solved = _segment_direction(skeleton, world, "left_upper_arm")
        np.testing.assert_allclose(
            solved, observed, atol=1e-6, err_msg=f"{label}: humerus does not follow the data"
        )

    # Abduction is ~90 degrees of arm travel: nearly straight down, to straight out.
    standing_direction = _segment_direction(skeleton, standing_world, "left_upper_arm")
    bent_direction = _segment_direction(skeleton, bent_world, "left_upper_arm")
    travel = math.degrees(
        math.acos(min(1.0, max(-1.0, float(np.dot(standing_direction, bent_direction)))))
    )
    assert 80.0 < travel < 100.0, f"humerus travelled {travel:.1f}°, expected ~90°"

    # ...and the trunk stayed put. `thoracic` is the spine redesign's chest segment.
    assert (
        _quat_angle_rad(standing_world["thoracic"], bent_world["thoracic"]) < 0.1
    ), "the trunk must not rotate with the arm"
