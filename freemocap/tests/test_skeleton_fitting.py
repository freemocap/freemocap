"""
Tests for the realtime skeleton fitting stack:

  - FABRIK tree solver (bone-length enforcement + settling convergence)
  - center-of-mass on the single canonical body model
  - full fitter create() and fit_frame() smoke test
"""

import numpy as np
import pytest

from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.fabrik_solver import (
    FabrikTree,
    solve_fabrik_tree,
)
from freemocap.core.tasks.mocap.realtime_skeleton_fitter import (
    RealtimeSkeletonFitter,
    _measure_lengths,
    _clamp_to_prior,
    _warm_start_positions,
    _solve_and_blend,
)
from freemocap.core.tasks.mocap.center_of_mass import (
    CoMConfidence,
    calculate_center_of_mass_per_frame,
    load_rtmpose_biomechanics,
)


# ---------------------------------------------------------------------------
# FABRIK solver
# ---------------------------------------------------------------------------


def test_fabrik_enforces_bone_lengths_and_is_idempotent_on_consistent_input():
    tree = FabrikTree.from_joint_hierarchy(joint_hierarchy={"root": ["mid"], "mid": ["tip"]})
    bone_lengths = {"root->mid": 100.0, "mid->tip": 80.0}
    targets = {
        "root": np.array([0.0, 0.0, 0.0]),
        "mid": np.array([0.0, 100.0, 0.0]),
        "tip": np.array([0.0, 180.0, 0.0]),
    }
    solved = solve_fabrik_tree(
        targets=targets, tree=tree, bone_lengths=bone_lengths,
        tolerance=0.1, max_iterations=20,
    )
    assert np.allclose(solved["root"], targets["root"])
    assert np.linalg.norm(solved["mid"] - solved["root"]) == pytest.approx(100.0, abs=1e-6)
    assert np.linalg.norm(solved["tip"] - solved["mid"]) == pytest.approx(80.0, abs=1e-6)
    for name in targets:
        assert np.allclose(solved[name], targets[name], atol=1e-6)
    solved_1 = solve_fabrik_tree(
        targets=targets, tree=tree, bone_lengths=bone_lengths,
        tolerance=0.1, max_iterations=1,
    )
    for name in targets:
        assert np.allclose(solved[name], solved_1[name], atol=1e-6)


def test_fabrik_converges_with_branches_before_max_iterations():
    tree = FabrikTree.from_joint_hierarchy(
        joint_hierarchy={"wrist": ["a1", "b1"], "a1": ["a2"], "b1": ["b2"]},
    )
    bl = {"wrist->a1": 50.0, "a1->a2": 40.0, "wrist->b1": 50.0, "b1->b2": 40.0}
    rng = np.random.default_rng(0)
    targets = {name: rng.normal(scale=120.0, size=3) for name in tree.topo_order}

    solved = solve_fabrik_tree(targets=targets, tree=tree, bone_lengths=bl,
                               tolerance=0.1, max_iterations=50)
    for bone_key, length in bl.items():
        parent, child = bone_key.split("->")
        assert np.linalg.norm(solved[child] - solved[parent]) == pytest.approx(length, abs=1e-3)
    solved_more = solve_fabrik_tree(targets=targets, tree=tree, bone_lengths=bl,
                                    tolerance=0.1, max_iterations=400)
    for name in tree.topo_order:
        assert np.allclose(solved[name], solved_more[name], atol=1e-3)


# ---------------------------------------------------------------------------
# New helpers (measure, clamp, warm-start, solve-and-blend)
# ---------------------------------------------------------------------------


def test_measure_lengths_computes_distances():
    tree = FabrikTree.from_joint_hierarchy(joint_hierarchy={"a": ["b"], "b": ["c"]})
    positions = {
        "a": np.array([0.0, 0.0, 0.0]),
        "b": np.array([0.0, 100.0, 0.0]),
        "c": np.array([0.0, 180.0, 0.0]),
    }
    lengths = _measure_lengths(positions, tree, fallback_priors={})
    assert lengths["a->b"] == pytest.approx(100.0)
    assert lengths["b->c"] == pytest.approx(80.0)


def test_measure_lengths_falls_back_to_priors():
    tree = FabrikTree.from_joint_hierarchy(joint_hierarchy={"a": ["b"]})
    positions = {"a": np.array([0.0, 0.0, 0.0])}  # missing b
    lengths = _measure_lengths(positions, tree, fallback_priors={"a->b": 150.0})
    assert lengths["a->b"] == 150.0


def test_clamp_to_prior_enforces_bounds():
    priors = {"a->b": 100.0}
    # Within bounds: passes through
    clamped = _clamp_to_prior({"a->b": 95.0}, priors, 0.2)
    assert clamped["a->b"] == 95.0
    # Below floor: clamped up
    clamped = _clamp_to_prior({"a->b": 50.0}, priors, 0.2)
    assert clamped["a->b"] == 80.0  # 100 * 0.8
    # Above ceiling: clamped down
    clamped = _clamp_to_prior({"a->b": 150.0}, priors, 0.2)
    assert clamped["a->b"] == 120.0  # 100 * 1.2


def test_warm_start_translates_previous_solution():
    prev = {"root": np.array([10.0, 0.0, 0.0]), "child": np.array([10.0, 100.0, 0.0])}
    targets = {"root": np.array([30.0, 0.0, 0.0]), "child": np.array([30.0, 100.0, 0.0])}
    result = _warm_start_positions(
        prev_solution=prev, targets=targets, root_names=("root",),
    )
    # Root moved +20 in X → everything translated by +20
    assert np.allclose(result["root"], [30.0, 0.0, 0.0])
    assert np.allclose(result["child"], [30.0, 100.0, 0.0])


def test_warm_start_returns_none_without_prev():
    result = _warm_start_positions(
        prev_solution=None,
        targets={"a": np.array([1.0, 2.0, 3.0])},
        root_names=("a",),
    )
    assert result is None


def test_solve_and_blend_applies_keypoint_blend():
    tree = FabrikTree.from_joint_hierarchy(joint_hierarchy={"root": ["child"]})
    targets = {
        "root": np.array([0.0, 0.0, 0.0]),
        "child": np.array([0.0, 100.0, 0.0]),
    }
    bone_lengths = {"root->child": 100.0}
    # keypoint_blend=0.0 → pure FABRIK
    fabrik_only = _solve_and_blend(
        targets=targets, tree=tree, bone_lengths=bone_lengths,
        tolerance=0.1, max_iterations=10, initial_positions=None,
        keypoint_blend_factor=0.0, center_blend_factor=0.0,
    )
    # keypoint_blend=1.0 → pure keypoints (FABRIK is a no-op)
    kp_only = _solve_and_blend(
        targets=targets, tree=tree, bone_lengths=bone_lengths,
        tolerance=0.1, max_iterations=10, initial_positions=None,
        keypoint_blend_factor=1.0, center_blend_factor=0.0,
    )
    # Pure keypoints should match targets exactly
    for name in targets:
        assert np.allclose(kp_only[name], targets[name], atol=1e-6)
    # Pure FABRIK should enforce bone lengths
    assert np.linalg.norm(fabrik_only["child"] - fabrik_only["root"]) == pytest.approx(100.0, abs=1e-3)
    # 0.6 blend should be between the two
    blended = _solve_and_blend(
        targets=targets, tree=tree, bone_lengths=bone_lengths,
        tolerance=0.1, max_iterations=10, initial_positions=None,
        keypoint_blend_factor=0.6, center_blend_factor=0.0,
    )
    # Blended child should be closer to keypoint target than pure FABRIK
    fabrik_child_dist = float(np.linalg.norm(fabrik_only["child"] - targets["child"]))
    blended_child_dist = float(np.linalg.norm(blended["child"] - targets["child"]))
    assert blended_child_dist < fabrik_child_dist or blended_child_dist == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Center of mass on the canonical body model
# ---------------------------------------------------------------------------


def _upright_rtmpose_pose() -> dict[str, np.ndarray]:
    """A crude upright standing pose in mm (RTMPose body keypoint names)."""
    def p(x, y, z):
        return np.array([float(x), float(y), float(z)])
    return {
        "left_ear": p(-60, 1700, 0), "right_ear": p(60, 1700, 0),
        "left_shoulder": p(-200, 1450, 0), "right_shoulder": p(200, 1450, 0),
        "left_elbow": p(-220, 1150, 0), "right_elbow": p(220, 1150, 0),
        "left_wrist": p(-230, 900, 0), "right_wrist": p(230, 900, 0),
        "left_hip": p(-120, 950, 0), "right_hip": p(120, 950, 0),
        "left_knee": p(-130, 500, 0), "right_knee": p(130, 500, 0),
        "left_ankle": p(-140, 80, 0), "right_ankle": p(140, 80, 0),
        "left_big_toe": p(-140, 20, 150), "right_big_toe": p(140, 20, 150),
    }


def test_center_of_mass_uses_canonical_model():
    bio = load_rtmpose_biomechanics()
    assert bio.segment_connections is not None
    assert bio.center_of_mass_definitions is not None
    assert bio.tracker_mapping is not None

    result = calculate_center_of_mass_per_frame(_upright_rtmpose_pose(), bio)
    com = result.total_body_com
    assert com.shape == (3,)
    assert np.all(np.isfinite(com))
    assert 80.0 < com[1] < 1700.0
    assert result.confidence >= CoMConfidence.medium


# ---------------------------------------------------------------------------
# Full fitter (needs skellyforge synced with all 26 body bone seeds)
# ---------------------------------------------------------------------------


def test_fitter_create_seeds_every_body_bone():
    from skellyforge.skellymodels.models.anatomical_structure import AnatomicalStructure
    from skellyforge.skellymodels.models.tracking_model_info import CanonicalBodyModelInfo

    body = AnatomicalStructure.from_model_info(CanonicalBodyModelInfo(), "body")
    ratios = body.bone_length_ratios or {}
    if len(ratios) < 26:
        pytest.skip(
            "canonical_body.yaml has <26 bone seeds — sync skellyforge into the "
            "freemocap venv to run the full fitter path."
        )

    fitter = RealtimeSkeletonFitter.create(height_mm=1750.0)
    assert len(fitter._body_tree.bone_keys) == 26
    for prior in fitter._static_body_priors.values():
        assert prior > 0.0
