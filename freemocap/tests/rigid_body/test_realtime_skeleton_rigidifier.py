"""Integration tests for the RealtimeSkeletonRigidifier.

Needs the live skellyforge canonical models (26 body bones / 20 hand bones) and
the skellytracker RTMPose->canonical mapping YAMLs in the venv.
"""
import numpy as np
import pytest

from freemocap.core.tasks.mocap.rigid_body.skeleton_rigidifier import RealtimeSkeletonRigidifier


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


def _frame(rig: RealtimeSkeletonRigidifier, pose: dict[str, np.ndarray], t: float):
    return rig.rigidify_frame(pose, measured=pose, t=t)


def test_create_seeds_all_bones():
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    assert len(rig.body_bone_lengths) == 26
    assert len(rig.right_hand_bone_lengths) == 20
    assert all(v > 0.0 for v in rig.body_bone_lengths.values())


def test_body_includes_canonical_centers():
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    out = _frame(rig, _upright_rtmpose_pose(), t=0.0)
    assert "hips_center" in out.body_positions
    assert "left_elbow" in out.body_positions


def test_output_segment_length_equals_estimate():
    # The rigid guarantee: an output bone's length is exactly the current
    # estimate, not whatever this frame's noisy observation happened to be.
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    out = _frame(rig, _upright_rtmpose_pose(), t=0.0)
    est = rig.body_bone_lengths["left_shoulder->left_elbow"]
    body = out.body_positions
    measured = float(np.linalg.norm(body["left_elbow"] - body["left_shoulder"]))
    assert measured == pytest.approx(est, abs=1e-6)


def test_segment_length_is_rigid_to_pose_change():
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    pose1 = _upright_rtmpose_pose()
    _frame(rig, pose1, t=0.0)
    # Bend the elbow drastically (very different observed upper-arm length).
    pose2 = dict(pose1)
    pose2["left_elbow"] = pose1["left_shoulder"] + np.array([0.0, -100.0, 0.0])
    out2 = _frame(rig, pose2, t=0.1)
    est = rig.body_bone_lengths["left_shoulder->left_elbow"]
    body = out2.body_positions
    measured = float(np.linalg.norm(body["left_elbow"] - body["left_shoulder"]))
    assert measured == pytest.approx(est, abs=1e-6)


def test_body_only_input_returns_empty_hands():
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    out = _frame(rig, _upright_rtmpose_pose(), t=0.0)  # no hand keypoints
    assert out.left_hand_positions == {}
    assert out.right_hand_positions == {}


def test_predicted_points_never_teach_lengths():
    # Gap-filled (extrapolated) keypoints are excluded from `measured`: the
    # rigidified output still uses them, but they cannot move the estimates.
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    pose = _upright_rtmpose_pose()
    seed = rig.body_bone_lengths["left_shoulder->left_elbow"]
    measured = dict(pose)
    del measured["left_elbow"]  # simulated: elbow extrapolated this frame
    for i in range(6):
        rig.rigidify_frame(pose, measured=measured, t=float(i))
    assert rig.body_bone_lengths["left_shoulder->left_elbow"] == pytest.approx(seed)


def test_lengths_track_measured_median():
    # Consistent observations pull each estimate to the observed length (the
    # rolling-window median), leaving the anthropometric seed behind.
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    pose = _upright_rtmpose_pose()
    seed = rig.body_bone_lengths["left_shoulder->left_elbow"]
    observed = float(np.linalg.norm(pose["left_elbow"] - pose["left_shoulder"]))
    for i in range(6):
        _frame(rig, pose, t=float(i))
    learned = rig.body_bone_lengths["left_shoulder->left_elbow"]
    assert learned == pytest.approx(observed)  # median of identical frames
    assert abs(learned - seed) > 1.0           # actually moved off the seed


def test_reset_clears_learned_lengths():
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    pose = _upright_rtmpose_pose()
    seed = rig.body_bone_lengths["left_shoulder->left_elbow"]
    for i in range(6):
        _frame(rig, pose, t=float(i))
    assert abs(rig.body_bone_lengths["left_shoulder->left_elbow"] - seed) > 1.0

    rig.reset()  # forget the rolling window -> back to seeds
    assert rig.body_bone_lengths["left_shoulder->left_elbow"] == pytest.approx(seed)
