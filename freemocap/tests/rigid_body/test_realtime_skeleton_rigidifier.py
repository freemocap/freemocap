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


def test_create_seeds_all_bones():
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    assert len(rig.body_bone_lengths) == 26
    assert len(rig.right_hand_bone_lengths) == 20
    assert all(v > 0.0 for v in rig.body_bone_lengths.values())


def test_body_includes_canonical_centers():
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    out = rig.rigidify_frame(_upright_rtmpose_pose())
    assert "hips_center" in out.body_positions
    assert "left_elbow" in out.body_positions


def test_output_segment_length_equals_estimate():
    # The rigid guarantee: an output bone's length is exactly the current
    # estimate, not whatever this frame's noisy observation happened to be.
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    out = rig.rigidify_frame(_upright_rtmpose_pose())
    est = rig.body_bone_lengths["left_shoulder->left_elbow"]
    body = out.body_positions
    measured = float(np.linalg.norm(body["left_elbow"] - body["left_shoulder"]))
    assert measured == pytest.approx(est, abs=1e-6)


def test_segment_length_is_rigid_to_pose_change():
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    pose1 = _upright_rtmpose_pose()
    rig.rigidify_frame(pose1)
    # Bend the elbow drastically (very different observed upper-arm length).
    pose2 = dict(pose1)
    pose2["left_elbow"] = pose1["left_shoulder"] + np.array([0.0, -100.0, 0.0])
    out2 = rig.rigidify_frame(pose2)
    est = rig.body_bone_lengths["left_shoulder->left_elbow"]
    body = out2.body_positions
    measured = float(np.linalg.norm(body["left_elbow"] - body["left_shoulder"]))
    assert measured == pytest.approx(est, abs=1e-6)


def test_body_only_input_returns_empty_hands():
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    out = rig.rigidify_frame(_upright_rtmpose_pose())  # no hand keypoints
    assert out.left_hand_positions == {}
    assert out.right_hand_positions == {}


def test_reset_forgets_learned_lengths():
    # Reset must drop learned bone lengths back to the anthropometric seeds, so
    # the next frame re-fits from scratch as if the pipeline had just started.
    rig = RealtimeSkeletonRigidifier.create(height_mm=1750.0)
    seed = rig.body_bone_lengths["left_shoulder->left_elbow"]
    rig.rigidify_frame(_upright_rtmpose_pose())
    learned = rig.body_bone_lengths["left_shoulder->left_elbow"]
    assert abs(learned - seed) > 1.0  # a real measurement replaced the seed

    rig.reset()

    assert rig.body_bone_lengths["left_shoulder->left_elbow"] == pytest.approx(seed)
