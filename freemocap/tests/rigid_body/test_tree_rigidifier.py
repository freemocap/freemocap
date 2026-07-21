"""Unit tests for the single-frame forward-pass tree rigidifier.

Mirrors skellyforge's posthoc ``rigidify_forward_pass``: walk the tree from the
root, keep each bone's observed *direction* (from the corrected parent toward the
observed child) but enforce its *length*, placing the child off the already-
corrected parent. Stateful: carries the last-good direction per bone so a
momentarily missing joint is gap-filled rather than collapsing.
"""
import numpy as np
import pytest

from freemocap.core.tasks.mocap.rigid_body.skeleton_rigidifier import TreeRigidifier


def _chain() -> TreeRigidifier:
    return TreeRigidifier(joint_hierarchy={"root": ["mid"], "mid": ["tip"]})


def test_enforces_exact_bone_lengths():
    rig = _chain()
    positions = {
        "root": np.array([0.0, 0.0, 0.0]),
        "mid": np.array([0.0, 120.0, 0.0]),   # observed 120, enforce 100
        "tip": np.array([0.0, 300.0, 0.0]),   # observed 180, enforce 80
    }
    out = rig.rigidify(positions, {"root->mid": 100.0, "mid->tip": 80.0})
    assert np.linalg.norm(out["mid"] - out["root"]) == pytest.approx(100.0)
    assert np.linalg.norm(out["tip"] - out["mid"]) == pytest.approx(80.0)


def test_keeps_observed_direction():
    rig = _chain()
    positions = {
        "root": np.array([0.0, 0.0, 0.0]),
        "mid": np.array([0.0, 120.0, 0.0]),
        "tip": np.array([0.0, 200.0, 0.0]),
    }
    out = rig.rigidify(positions, {"root->mid": 100.0, "mid->tip": 80.0})
    assert np.allclose(out["root"], [0.0, 0.0, 0.0])
    assert np.allclose(out["mid"], [0.0, 100.0, 0.0])
    assert np.allclose(out["tip"], [0.0, 180.0, 0.0])


def test_root_anchored_at_observed_position():
    rig = _chain()
    positions = {
        "root": np.array([5.0, 5.0, 5.0]),
        "mid": np.array([5.0, 125.0, 5.0]),
        "tip": np.array([5.0, 205.0, 5.0]),
    }
    out = rig.rigidify(positions, {"root->mid": 100.0, "mid->tip": 80.0})
    assert np.allclose(out["root"], [5.0, 5.0, 5.0])


def test_missing_child_gapfilled_from_last_direction():
    rig = _chain()
    bl = {"root->mid": 100.0, "mid->tip": 80.0}
    # Frame 1 establishes the (0,1,0) direction for both bones.
    rig.rigidify(
        {"root": np.array([0.0, 0.0, 0.0]), "mid": np.array([0.0, 120.0, 0.0]),
         "tip": np.array([0.0, 200.0, 0.0])},
        bl,
    )
    # Frame 2: mid + tip missing -> gap-filled from carried direction.
    out = rig.rigidify({"root": np.array([0.0, 0.0, 0.0])}, bl)
    assert np.allclose(out["mid"], [0.0, 100.0, 0.0])
    assert np.allclose(out["tip"], [0.0, 180.0, 0.0])


def test_idempotent_on_already_rigid_input():
    rig = _chain()
    bl = {"root->mid": 100.0, "mid->tip": 80.0}
    positions = {
        "root": np.array([0.0, 0.0, 0.0]),
        "mid": np.array([0.0, 100.0, 0.0]),
        "tip": np.array([0.0, 180.0, 0.0]),
    }
    out = rig.rigidify(positions, bl)
    for name, pos in positions.items():
        assert np.allclose(out[name], pos)


def test_branch_point_children_placed_independently():
    rig = TreeRigidifier(joint_hierarchy={"root": ["a", "b"]})
    positions = {
        "root": np.array([0.0, 0.0, 0.0]),
        "a": np.array([50.0, 0.0, 0.0]),
        "b": np.array([0.0, 0.0, 50.0]),
    }
    out = rig.rigidify(positions, {"root->a": 30.0, "root->b": 40.0})
    assert np.allclose(out["a"], [30.0, 0.0, 0.0])
    assert np.allclose(out["b"], [0.0, 0.0, 40.0])


def test_returns_empty_when_root_missing():
    rig = _chain()
    out = rig.rigidify({"mid": np.array([0.0, 120.0, 0.0])}, {"root->mid": 100.0, "mid->tip": 80.0})
    assert out == {}
