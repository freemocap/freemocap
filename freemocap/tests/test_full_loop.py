"""F5a — the full realtime loop, backend half of the gate.

Synthetic rtmpose keypoints → the real rigidifier → the real orientation solver
→ a real aggregator message → sample bytes → decode → the wire rotations equal
the solver's, and a mock-camera standing run yields **non-NaN ROTATIONS_WORLD**
for every solved segment. An arm-abduction frame set then shows the change
lands where it should: the humerus rotates ~90° while the spine stays put.

This is the backend half of F5; the frontend integration test and the user's
manual run are the other halves.
"""
from __future__ import annotations

import math

import numpy as np

# NOTE the import order matters: ``realtime_pipeline_config`` must NOT be the
# first freemocap import — importing it first trips a circular import through
# ``pubsub_topics`` (``pubsub_topics`` imports the config; if the config is
# still mid-init, the re-import finds it partially initialized).
from freemocap.core.streaming.standard_stream import (
    ChannelKind,
    StreamSample,
    StreamSchema,
    decode_sample,
)
from freemocap.core.streaming.standard_stream.producers import compose, compose_sample
from freemocap.core.streaming.standard_stream.producers.producer_contexts import (
    FrameContext,
    StreamContext,
)
from freemocap.core.tasks.mocap.center_of_mass import (
    CoMConfidence,
    CenterOfMassResult,
)
from freemocap.core.pipeline.realtime.realtime_pipeline_config import (
    RealtimePipelineConfig,
)
from freemocap.pubsub.pubsub_topics import (
    AggregationNodeOutputMessage,
    CameraNodeOutputMessage,
)
from freemocap.core.tasks.mocap.rigid_body.skeleton_rigidifier import (
    RealtimeSkeletonRigidifier,
)
from freemocap.core.tasks.mocap.tracker_mappings import tracker_keypoint_names
from skellyforge.data_models.trajectory_3d import Point3d
from skellyforge.kinematics.orientation_solver import (
    FrameOrientationResult,
    solve_frame_orientations,
)
from skellyforge.skellymodels.standard_human.reference_geometry import (
    build_reference_geometry,
)
from skellyforge.skellymodels.standard_human.standard_human_model import (
    StandardHuman,
    compose_standard_human,
)
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import (
    Observation,
    StageObservation,
)

NOMINAL_HEIGHT_MM = 1750.0


def _standing_pose() -> dict[str, np.ndarray]:
    """A standing rtmpose-named pose (mm, +Y-up).

    NOT the model's T-pose — proportions differ from the reference geometry, so
    the solved world quaternions are finite near-identity values, not exact
    identity (the exact identity-at-T-pose contract lives in skellyforge's own
    tests). The gate asks for a realistic stream that solves without NaN.
    """

    def p(x: float, y: float, z: float) -> np.ndarray:
        return np.array([float(x), float(y), float(z)])

    return {
        "nose": p(0, 1720, 0),
        "left_eye": p(-30, 1730, 0),
        "right_eye": p(30, 1730, 0),
        "left_ear": p(-60, 1700, 0),
        "right_ear": p(60, 1700, 0),
        "left_shoulder": p(-200, 1450, 0),
        "right_shoulder": p(200, 1450, 0),
        "left_elbow": p(-220, 1150, 0),
        "right_elbow": p(220, 1150, 0),
        "left_wrist": p(-230, 900, 0),
        "right_wrist": p(230, 900, 0),
        "left_hip": p(-120, 950, 0),
        "right_hip": p(120, 950, 0),
        "left_knee": p(-130, 500, 0),
        "right_knee": p(130, 500, 0),
        "left_ankle": p(-140, 80, 0),
        "right_ankle": p(140, 80, 0),
        "left_big_toe": p(-140, 20, 150),
        "right_big_toe": p(140, 20, 150),
        "left_small_toe": p(-160, 20, 140),
        "right_small_toe": p(160, 20, 140),
        "left_heel": p(-140, 40, -40),
        "right_heel": p(140, 40, -40),
    }


def _abducted_left_arm(pose: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """The standing pose with the left arm abducted 90° (elbow/wrist out to −X)."""
    out = {name: pos.copy() for name, pos in pose.items()}
    shoulder = pose["left_shoulder"]
    out["left_elbow"] = shoulder + np.array([-300.0, 0.0, 0.0])
    out["left_wrist"] = shoulder + np.array([-600.0, 0.0, 0.0])
    return out


def _observation(
    *, frame_number: int, body_points: dict[str, tuple[float, float]]
) -> Observation:
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


def _solver_input(result) -> dict[str, np.ndarray]:
    """The exact keypoint merge the aggregator feeds the solver."""
    return {
        **result.body_positions,
        **result.left_hand_standard_positions,
        **result.right_hand_standard_positions,
    }


def _measured_lengths(
    model: StandardHuman, rig: RealtimeSkeletonRigidifier
) -> dict[str, float]:
    """The aggregator's segment-length merge: measured + nominal face fallback."""
    lengths: dict[str, float] = {
        **rig.body_segment_lengths,
        **rig.left_hand_segment_lengths,
        **rig.right_hand_segment_lengths,
    }
    for seg in model.segments:
        if seg.name not in lengths:
            lengths[seg.name] = seg.length_ratio * NOMINAL_HEIGHT_MM
    return lengths


def _solve(
    model: StandardHuman,
    rig: RealtimeSkeletonRigidifier,
    pose: dict[str, np.ndarray],
    *,
    n_frames: int = 30,
    dt: float = 1.0,
) -> FrameOrientationResult:
    """Feed ``n`` identical frames, then solve the last frame (damped)."""
    result = None
    for i in range(n_frames):
        result = rig.rigidify_frame(pose, measured=pose, t=float(i) * dt)
    lengths = _measured_lengths(model, rig)
    reference_geometry = build_reference_geometry(
        list(model.segments), lengths
    ).segments
    return solve_frame_orientations(
        standard_human=model,
        reference_geometry=reference_geometry,
        landmarks=_solver_input(result),
        timestamp_seconds=float(n_frames - 1) * dt,
        previous_result=None,
    )


def _message(
    model: StandardHuman,
    result,
    orientation: FrameOrientationResult,
    pose: dict[str, np.ndarray],
    lengths: dict[str, float],
) -> AggregationNodeOutputMessage:
    """A real aggregator message: tracker keypoints + rigidified landmarks +
    solved rotations + two mock cameras."""
    com = CenterOfMassResult(
        total_body_com=np.zeros(3),
        segment_coms={},
        directly_observed_mass=1.0,
        confidence=CoMConfidence.high,
    )
    return AggregationNodeOutputMessage(
        frame_number=7,
        pipeline_config=RealtimePipelineConfig(),
        camera_group_id="cg-0",
        camera_node_outputs={
            "cam-0": CameraNodeOutputMessage(
                camera_id="cam-0",
                frame_number=7,
                skeleton_observation=_observation(
                    frame_number=7,
                    body_points={"nose": (320.0, 240.0), "left_shoulder": (100.0, 200.0)},
                ),
            ),
            "cam-1": CameraNodeOutputMessage(
                camera_id="cam-1",
                frame_number=7,
                skeleton_observation=_observation(
                    frame_number=7,
                    body_points={"nose": (310.0, 250.0)},
                ),
            ),
        },
        keypoints_arrays=pose,
        center_of_mass_result=com,
        xcom=Point3d(x=0.0, y=0.0, z=0.0),
        skeleton=None,
        standard_skeleton=_solver_input(result),
        segment_rotations_world=orientation.world_quaternions,
        segment_rotations_local=orientation.local_quaternions,
        segment_lengths=lengths,
    )


def _schema(model: StandardHuman) -> StreamSchema:
    """The composed schema; live lengths ride the per-frame SEGMENT_LENGTHS block."""
    return compose(
        StreamContext(
            standard_human=model,
            camera_ids=("cam-0", "cam-1"),
            tracker_keypoint_names=tracker_keypoint_names("rtmpose"),
            pipeline_live=True,
        ),
        stream_id="loop",
        stream_name="full-loop",
    ).schema


def _block_by_kind(sample: StreamSample, kind: ChannelKind):
    return [b for b in sample.blocks if b.kind is kind]


def _quat_angle_rad(a: np.ndarray, b: np.ndarray) -> float:
    """The rotation angle between two unit quaternions (shortest arc)."""
    dot = abs(float(np.dot(a, b)))
    return 2.0 * math.acos(min(1.0, dot))


# ── The gate ──────────────────────────────────────────────────────────────


def test_full_loop_wire_rotations_equal_solver_and_are_finite():
    """aggregator → sample → bytes → decode: rotations identical + non-NaN."""
    model = compose_standard_human()
    rig = RealtimeSkeletonRigidifier.create(
        standard_human=model, detector_type="rtmpose", height_mm=NOMINAL_HEIGHT_MM
    )
    pose = _standing_pose()
    orientation = _solve(model, rig, pose)

    # Every solved segment's world quaternion is finite — the mock-camera gate.
    world = orientation.world_quaternions
    assert world, "the standing pose must solve segments"
    for name, q in world.items():
        assert np.all(np.isfinite(q)), f"ROTATIONS_WORLD non-finite for {name}"
        assert abs(float(np.linalg.norm(q)) - 1.0) < 1e-6, f"non-unit quaternion for {name}"

    result = rig.rigidify_frame(pose, measured=pose, t=100.0)
    lengths = _measured_lengths(model, rig)
    message = _message(model, result, orientation, pose, lengths)
    sample = compose_sample(
        compose(
            StreamContext(
                standard_human=model,
                camera_ids=("cam-0", "cam-1"),
                tracker_keypoint_names=tracker_keypoint_names("rtmpose"),
                pipeline_live=True,
            ),
            stream_id="loop",
            stream_name="full-loop",
        ),
        FrameContext(
            frame_number=message.frame_number,
            timestamp=0.0,
            aggregator_output=message,
        ),
    )
    restored = StreamSample.from_bytes(sample.to_bytes())

    # Wire ROTATIONS_WORLD rows equal the solver's quaternions (float32 wire).
    (world_block,) = _block_by_kind(restored, ChannelKind.ROTATIONS_WORLD)
    group = _schema(model).channels[4]
    name_to_idx = {n: i for i, n in enumerate(group.names)}
    for name, q in world.items():
        row = world_block.data[name_to_idx[name]]
        np.testing.assert_allclose(row, np.asarray(q, dtype=np.float32), atol=1e-6)

    # LANDMARKS_3D carries the rigidified hips_center.
    (lm_block,) = _block_by_kind(restored, ChannelKind.LANDMARKS_3D)
    lm_names = _schema(model).channels[1].names
    hips_idx = lm_names.index("hips_center")
    np.testing.assert_allclose(
        lm_block.data[hips_idx, :3], result.body_positions["hips_center"], atol=1e-4
    )

    # KEYPOINTS_3D carries the tracker-named nose measurement.
    (kp_block,) = _block_by_kind(restored, ChannelKind.KEYPOINTS_3D)
    kp_names = _schema(model).channels[0].names
    nose_idx = kp_names.index("nose")
    np.testing.assert_allclose(
        kp_block.data[nose_idx, :3], pose["nose"], atol=1e-4
    )


def test_arm_abduction_rotates_humerus_and_leaves_spine():
    """The change lands where it should: ~90° on the humerus, ~0° on the spine."""
    model = compose_standard_human()
    rig = RealtimeSkeletonRigidifier.create(
        standard_human=model, detector_type="rtmpose", height_mm=NOMINAL_HEIGHT_MM
    )
    standing = _solve(model, rig, _standing_pose())
    bent = _solve(model, rig, _abducted_left_arm(_standing_pose()))

    standing_humerus = standing.world_quaternions["left_upper_arm"]
    bent_humerus = bent.world_quaternions["left_upper_arm"]
    angle = _quat_angle_rad(standing_humerus, bent_humerus)
    assert abs(angle - math.pi / 2) < 0.2, f"humerus rotated {math.degrees(angle):.1f}°, expected ~90°"

    standing_spine = standing.world_quaternions["spine"]
    bent_spine = bent.world_quaternions["spine"]
    assert _quat_angle_rad(standing_spine, bent_spine) < 0.1, "spine must not rotate with the arm"
