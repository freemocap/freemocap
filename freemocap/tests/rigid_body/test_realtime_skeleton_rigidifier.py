"""Integration tests for the RealtimeSkeletonRigidifier.

Needs the live skellyforge standard-human model and the skellytracker
RTMPose->standard-human mapping YAMLs in the venv.
"""
import numpy as np
import pytest

from skellyforge.skellymodels.standard_human.standard_human_model import (
    compose_standard_human,
)

from freemocap.core.tasks.mocap.rigid_body.skeleton_rigidifier import (
    RealtimeSkeletonRigidifier,
)


def _upright_rtmpose_pose() -> dict[str, np.ndarray]:
    """A crude upright standing pose in mm (RTMPose body keypoint names)."""
    def p(x, y, z):
        return np.array([float(x), float(y), float(z)])
    return {
        "nose": p(0, 1720, 0),
        "left_eye": p(-30, 1730, 0), "right_eye": p(30, 1730, 0),
        "left_ear": p(-60, 1700, 0), "right_ear": p(60, 1700, 0),
        "left_shoulder": p(-200, 1450, 0), "right_shoulder": p(200, 1450, 0),
        "left_elbow": p(-220, 1150, 0), "right_elbow": p(220, 1150, 0),
        "left_wrist": p(-230, 900, 0), "right_wrist": p(230, 900, 0),
        "left_hip": p(-120, 950, 0), "right_hip": p(120, 950, 0),
        "left_knee": p(-130, 500, 0), "right_knee": p(130, 500, 0),
        "left_ankle": p(-140, 80, 0), "right_ankle": p(140, 80, 0),
        "left_big_toe": p(-140, 20, 150), "right_big_toe": p(140, 20, 150),
        "left_small_toe": p(-160, 20, 140), "right_small_toe": p(160, 20, 140),
        "left_heel": p(-140, 40, -40), "right_heel": p(140, 40, -40),
    }


@pytest.fixture
def rigidifier() -> RealtimeSkeletonRigidifier:
    return RealtimeSkeletonRigidifier.create(
        standard_human=compose_standard_human(), height_mm=1750.0
    )


def _frame(rig: RealtimeSkeletonRigidifier, pose: dict[str, np.ndarray], t: float):
    return rig.rigidify_frame(pose, measured=pose, t=t)


def test_create_seeds_all_segments(rigidifier):
    # 20 body segments + 16 per hand. Keys are SEGMENT names, not arrow keys.
    assert len(rigidifier.body_segment_lengths) == 20
    assert len(rigidifier.right_hand_segment_lengths) == 16
    assert len(rigidifier.left_hand_segment_lengths) == 16
    assert all(v > 0.0 for v in rigidifier.body_segment_lengths.values())
    assert all("->" not in k for k in rigidifier.body_segment_lengths)
    assert all("->" not in k for k in rigidifier.right_hand_segment_lengths)
    assert all("->" not in k for k in rigidifier.left_hand_segment_lengths)


def test_body_includes_canonical_centers(rigidifier):
    out = _frame(rigidifier, _upright_rtmpose_pose(), t=0.0)
    assert "hips_center" in out.body_positions
    assert "left_elbow" in out.body_positions


def test_body_lengths_keyed_by_segment_names(rigidifier):
    # (b) — no arrow keys anywhere in the rigidifier's public outputs.
    assert all("->" not in k for k in rigidifier.body_segment_lengths)
    assert all("->" not in k for k in rigidifier.right_hand_segment_lengths)
    assert all("->" not in k for k in rigidifier.left_hand_segment_lengths)


def test_head_vertex_sits_one_head_length_above_head_center(rigidifier):
    # (a) — a straight standing pose's corrected head_vertex sits ~
    # head.length_ratio × height above the corrected head_center.
    rig = rigidifier
    head_ratio = next(
        s.length_ratio
        for s in compose_standard_human().segments
        if s.name == "head"
    )
    out = _frame(rig, _upright_rtmpose_pose(), t=0.0)
    head_center = out.body_positions["head_center"]
    head_vertex = out.body_positions["head_vertex"]
    span = float(np.linalg.norm(head_vertex - head_center))
    assert span == pytest.approx(head_ratio * 1750.0, rel=0.1)


def test_output_segment_length_equals_estimate(rigidifier):
    # The rigid guarantee: an output segment's length is exactly the current
    # estimate, not whatever this frame's noisy observation happened to be.
    out = _frame(rigidifier, _upright_rtmpose_pose(), t=0.0)
    est = rigidifier.body_segment_lengths["left_upper_arm"]
    body = out.body_positions
    measured = float(np.linalg.norm(body["left_elbow"] - body["left_shoulder"]))
    assert measured == pytest.approx(est, abs=1e-6)


def test_segment_length_is_rigid_to_pose_change(rigidifier):
    rig = rigidifier
    pose1 = _upright_rtmpose_pose()
    _frame(rig, pose1, t=0.0)
    # Bend the elbow drastically (very different observed upper-arm length).
    pose2 = dict(pose1)
    pose2["left_elbow"] = pose1["left_shoulder"] + np.array([0.0, -100.0, 0.0])
    out2 = _frame(rig, pose2, t=0.1)
    est = rig.body_segment_lengths["left_upper_arm"]
    body = out2.body_positions
    measured = float(np.linalg.norm(body["left_elbow"] - body["left_shoulder"]))
    assert measured == pytest.approx(est, abs=1e-6)


def test_body_only_input_returns_empty_hands(rigidifier):
    out = _frame(rigidifier, _upright_rtmpose_pose(), t=0.0)  # no hand keypoints
    assert out.left_hand_positions == {}
    assert out.right_hand_positions == {}


def test_predicted_points_never_teach_lengths(rigidifier):
    # Gap-filled (extrapolated) keypoints are excluded from `measured`: the
    # rigidified output still uses them, but they cannot move the estimates.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    seed = rig.body_segment_lengths["left_upper_arm"]
    measured = dict(pose)
    del measured["left_elbow"]  # simulated: elbow extrapolated this frame
    for i in range(6):
        rig.rigidify_frame(pose, measured=measured, t=float(i))
    assert rig.body_segment_lengths["left_upper_arm"] == pytest.approx(seed)


def test_lengths_track_measured_median(rigidifier):
    # Consistent observations pull each estimate to the observed length (the
    # rolling-window median), leaving the anthropometric seed behind.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    seed = rig.body_segment_lengths["left_upper_arm"]
    observed = float(np.linalg.norm(pose["left_elbow"] - pose["left_shoulder"]))
    for i in range(6):
        _frame(rig, pose, t=float(i))
    learned = rig.body_segment_lengths["left_upper_arm"]
    assert learned == pytest.approx(observed)  # median of identical frames
    assert abs(learned - seed) > 1.0           # actually moved off the seed


def test_reset_clears_learned_lengths(rigidifier):
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    seed = rig.body_segment_lengths["left_upper_arm"]
    for i in range(6):
        _frame(rig, pose, t=float(i))
    assert abs(rig.body_segment_lengths["left_upper_arm"] - seed) > 1.0

    rig.reset()  # forget the rolling window -> back to seeds
    assert rig.body_segment_lengths["left_upper_arm"] == pytest.approx(seed)


def test_face_nose_passes_through_uncorrected(rigidifier):
    # The face's ``nose`` long-axis keypoint is a shared direction reference —
    # it passes through at the observed position, NOT extruded to a length.
    pose = _upright_rtmpose_pose()
    out = _frame(rigidifier, pose, t=0.0)
    observed_nose = np.array([0.0, 1720.0, 0.0])
    assert np.allclose(out.body_positions["nose"], observed_nose, atol=1e-6)


def test_face_ears_present_at_observed(rigidifier):
    pose = _upright_rtmpose_pose()
    out = _frame(rigidifier, pose, t=0.0)
    assert np.allclose(out.body_positions["left_ear"], pose["left_ear"], atol=1e-6)
    assert np.allclose(out.body_positions["right_ear"], pose["right_ear"], atol=1e-6)


def test_all_eight_face_keypoints_survive(rigidifier):
    # The face's eight segments are childless roots in the body tree — their
    # origin keypoints (left_eye / right_eye / jaw / left_mouth / right_mouth)
    # never equal ``head``'s long axis, so the tree never anchors them and their
    # origins would silently vanish without the wrapper-side observed fallback.
    # Fully observed: ALL EIGHT face keypoints must appear in body_positions.
    pose = _upright_rtmpose_pose()
    out = _frame(rigidifier, pose, t=0.0)
    body = out.body_positions

    # Tracked keypoints: equal to the observed position.
    for name in ("nose", "left_eye", "right_eye", "left_ear", "right_ear"):
        assert np.allclose(body[name], pose[name], atol=1e-6), name

    # Derived keypoints (from the mapping's anatomical_offset entries — NOT in
    # the raw pose) must be present and finite.
    for name in ("jaw", "left_mouth", "right_mouth"):
        assert name in body, name
        assert np.all(np.isfinite(body[name])), name

    # Sanity: the jaw sits below the nose (mouth below nose in a standing pose).
    assert body["jaw"][1] < body["nose"][1]



def test_left_hip_anchored_at_observed(rigidifier):
    # ``left_upper_leg`` is ORIGIN-attached (origin ``left_hip`` ≠ ``hips``'s
    # long axis ``trunk_center``), so it is a root anchored at its observed
    # position — ``left_hip`` is not displaced by the tree.
    pose = _upright_rtmpose_pose()
    out = _frame(rigidifier, pose, t=0.0)
    assert np.allclose(out.body_positions["left_hip"], pose["left_hip"], atol=1e-6)


def test_hips_center_not_displaced(rigidifier):
    # With the old degenerate ``hips→spine`` same-keypoint edge gone, ``spine``
    # is now a root and ``hips_center`` stays at its observed position.
    pose = _upright_rtmpose_pose()
    out = _frame(rigidifier, pose, t=0.0)
    observed_hips_center = np.mean([pose["left_hip"], pose["right_hip"]], axis=0)
    assert np.allclose(out.body_positions["hips_center"], observed_hips_center, atol=1e-6)
