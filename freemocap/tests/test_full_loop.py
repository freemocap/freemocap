"""F5a — the full realtime loop, backend half of the gate (message path).

Synthetic rtmpose keypoints -> the real tracker mapping + rigidifier -> the real
orientation solver -> a real aggregator message -> a self-describing frame message ->
CBOR -> the wire rotations equal the solver's, and a mock-camera standing run yields
non-NaN ROTATIONS_WORLD for every solved segment. An arm-abduction frame set then shows
the change lands where it should: the humerus rotates ~90° while the spine stays put.

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
from freemocap.core.streaming.message_model import ChannelKind, encode_message
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext
from skellyforge.kinematics.inertial.center_of_mass import (
    CenterOfMassResult,
    CoMConfidence,
)
from freemocap.core.tasks.mocap.tracker_mappings import load_standard_human_mapping
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.pubsub.pubsub_topics import (
    AggregationNodeOutputMessage,
    CameraNodeOutputMessage,
)
from freemocap.core.tasks.mocap.tracker_mappings import tracker_keypoint_names
from skellyforge.data_models.trajectory_3d import Point3d
from skellyforge.kinematics.orientation_solver import (
    FrameOrientationResult,
    SolveState,
    solve_frame_orientations,
)
from skellyforge.kinematics.segment_length_estimation import (
    SegmentLengthState,
    estimate_segment_lengths,
)
from skellyforge.kinematics.skeleton_rigidifier import rigidify_landmarks
from skellyforge.kinematics.tpose import build_standard_human_tpose
from skellyforge.skellymodels.standard_human.human_skeleton import HumanSkeleton
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import (
    Observation,
    StageObservation,
)


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
    """A minimal per-camera skeleton Observation with a body stage."""
    names = tuple(body_points.keys())
    xyz = np.array([(x, y, 0.0) for x, y in body_points.values()], dtype=np.float64)
    visibility = np.full(len(names), 1.0)
    kp = Keypoints(names=names, xyz=xyz, visibility=visibility)
    return Observation(
        frame_number=frame_number,
        image_size=(480, 640),
        stages={"body": StageObservation(name="body", keypoints=kp)},
    )


def _solve(
    skeleton: HumanSkeleton,
    pose: dict[str, np.ndarray],
    *,
    n_frames: int = 30,
    dt: float = 1.0,
) -> tuple[FrameOrientationResult, dict[str, np.ndarray], dict[str, float]]:
    """The aggregator's exact reconstruction order, run n identical frames.

    tracker mapping -> estimate lengths -> build T-pose -> rigidify -> solve,
    threading the solve + length state across frames so the damped tier settles.
    """
    mapping = load_standard_human_mapping("rtmpose")
    mapped = mapping(pose)

    orientation_state = SolveState()
    length_state = SegmentLengthState.empty()
    orientation: FrameOrientationResult | None = None
    rigid: dict[str, np.ndarray] | None = None
    lengths: dict[str, float] = {}

    for i in range(n_frames):
        length_result, length_state = estimate_segment_lengths(
            skeleton,
            mapped,
            timestamp_seconds=float(i) * dt,
            window_seconds=2.5,
            state=length_state,
        )
        lengths = length_result.lengths
        tpose = build_standard_human_tpose(skeleton, lengths)
        rigid = rigidify_landmarks(skeleton, tpose, mapped)
        orientation, orientation_state = solve_frame_orientations(
            skeleton,
            tpose,
            rigid,
            timestamp_seconds=float(i) * dt,
            state=orientation_state,
        )

    assert orientation is not None and rigid is not None
    return orientation, rigid, lengths


def _message(
    model: HumanSkeleton,
    result: dict[str, np.ndarray],
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
        skeleton=result,
        standard_skeleton=result,
        segment_rotations_world=orientation.world_quaternions,
        segment_rotations_local=orientation.local_quaternions,
        segment_lengths=lengths,
    )


def _frame_message(model, result, orientation, pose, lengths) -> dict:
    """Compose the self-describing frame message, encode, and CBOR-decode."""
    composition = compose_messages(
        StreamContext(
            standard_human=model,
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
            aggregator_output=_message(model, result, orientation, pose, lengths),
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
    model = HumanSkeleton.standard_human()
    pose = _standing_pose()
    orientation, result, lengths = _solve(model, pose)

    world = orientation.world_quaternions
    assert world, "the standing pose must solve segments"
    for name, q in world.items():
        assert np.all(np.isfinite(q)), f"ROTATIONS_WORLD non-finite for {name}"
        assert abs(float(np.linalg.norm(q)) - 1.0) < 1e-6, f"non-unit quaternion for {name}"

    restored = _frame_message(model, result, orientation, pose, lengths)

    # ROTATIONS_WORLD rows equal the solver's quaternions (float32 wire).
    world_channel = _channel_by_kind(restored, "ROTATIONS_WORLD")
    world_data = _channel_data(world_channel, 4)
    # ROTATIONS_WORLD is index-keyed against the model's segment order.
    name_to_idx = {n: i for i, n in enumerate(model.segment_names)}
    for name, q in world.items():
        np.testing.assert_allclose(
            world_data[name_to_idx[name]], np.asarray(q, dtype=np.float32), atol=1e-6
        )

    # LANDMARKS_3D carries the rigidified hips_center.
    lm_channel = _channel_by_kind(restored, "LANDMARKS_3D")
    lm_data = _channel_data(lm_channel, 4)
    # LANDMARKS_3D is index-keyed against the sorted landmark order.
    hips_idx = model.landmark_names.index("hips_center")
    np.testing.assert_allclose(
        lm_data[hips_idx, :3], result["hips_center"], atol=1e-4
    )

    # KEYPOINTS_3D carries the tracker-named nose measurement.
    kp_channel = _channel_by_kind(restored, "KEYPOINTS_3D")
    kp_data = _channel_data(kp_channel, 4)
    nose_idx = kp_channel["names"].index("nose")
    np.testing.assert_allclose(kp_data[nose_idx, :3], pose["nose"], atol=1e-4)


def test_arm_abduction_rotates_humerus_and_leaves_spine():
    """The change lands where it should: ~90° on the humerus, ~0° on the spine."""
    model = HumanSkeleton.standard_human()
    standing = _solve(model, _standing_pose())[0]
    bent = _solve(model, _abducted_left_arm(_standing_pose()))[0]

    standing_humerus = standing.world_quaternions["left_upper_arm"]
    bent_humerus = bent.world_quaternions["left_upper_arm"]
    angle = _quat_angle_rad(standing_humerus, bent_humerus)
    assert abs(angle - math.pi / 2) < 0.2, f"humerus rotated {math.degrees(angle):.1f}°, expected ~90°"

    standing_spine = standing.world_quaternions["spine"]
    bent_spine = bent.world_quaternions["spine"]
    assert _quat_angle_rad(standing_spine, bent_spine) < 0.1, "spine must not rotate with the arm"
