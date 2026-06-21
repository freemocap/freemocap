"""
Tests for the canonical-skeleton realtime fitting stack:

  - FABRIK tree solver (bone-length enforcement + settling convergence)
  - online bone-length seeding/adaptation (Welford)
  - derived-center bones are observed and self-consistent
  - center-of-mass on the single canonical body model

These exercise the pure logic and the COM path, which run against the
installed canonical model. The full ``RealtimeSkeletonFitter.create()`` path
additionally needs skellyforge synced with all 26 body bone-length seeds
(see ``test_fitter_create_seeds_every_body_bone``, which skips otherwise).
"""

import numpy as np
import pytest

from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.fabrik_solver import (
    FabrikTree,
    solve_fabrik_tree,
)
from freemocap.core.tasks.mocap.realtime_skeleton_fitter import (
    RealtimeSkeletonFitter,
    _WelfordTracker,
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
    # Targets already satisfy the bone lengths (colinear at exact distances).
    targets = {
        "root": np.array([0.0, 0.0, 0.0]),
        "mid": np.array([0.0, 100.0, 0.0]),
        "tip": np.array([0.0, 180.0, 0.0]),
    }
    solved = solve_fabrik_tree(
        targets=targets, tree=tree, bone_lengths=bone_lengths,
        tolerance=0.1, max_iterations=20,
    )
    # Root stays fixed; bone lengths are enforced exactly.
    assert np.allclose(solved["root"], targets["root"])
    assert np.linalg.norm(solved["mid"] - solved["root"]) == pytest.approx(100.0, abs=1e-6)
    assert np.linalg.norm(solved["tip"] - solved["mid"]) == pytest.approx(80.0, abs=1e-6)
    # Consistent input → output equals input.
    for name in targets:
        assert np.allclose(solved[name], targets[name], atol=1e-6)
    # Early-exit: a single iteration already gives the converged answer.
    solved_1 = solve_fabrik_tree(
        targets=targets, tree=tree, bone_lengths=bone_lengths,
        tolerance=0.1, max_iterations=1,
    )
    for name in targets:
        assert np.allclose(solved[name], solved_1[name], atol=1e-6)


def test_fabrik_converges_with_branches_before_max_iterations():
    # Y-split: wrist → two finger chains.
    tree = FabrikTree.from_joint_hierarchy(
        joint_hierarchy={"wrist": ["a1", "b1"], "a1": ["a2"], "b1": ["b2"]},
    )
    bl = {"wrist->a1": 50.0, "a1->a2": 40.0, "wrist->b1": 50.0, "b1->b2": 40.0}
    rng = np.random.default_rng(0)
    targets = {name: rng.normal(scale=120.0, size=3) for name in tree.topo_order}

    solved = solve_fabrik_tree(targets=targets, tree=tree, bone_lengths=bl,
                               tolerance=0.1, max_iterations=50)
    # Output respects every bone length.
    for bone_key, length in bl.items():
        parent, child = bone_key.split("->")
        assert np.linalg.norm(solved[child] - solved[parent]) == pytest.approx(length, abs=1e-3)
    # Converged before 50 iterations: running far longer changes nothing.
    solved_more = solve_fabrik_tree(targets=targets, tree=tree, bone_lengths=bl,
                                    tolerance=0.1, max_iterations=400)
    for name in tree.topo_order:
        assert np.allclose(solved[name], solved_more[name], atol=1e-3)


# ---------------------------------------------------------------------------
# Online bone-length seeding / adaptation
# ---------------------------------------------------------------------------


def test_welford_blends_from_seed_toward_observation():
    tracker = _WelfordTracker(prior=100.0)
    # No observations → stays at the seed.
    assert tracker.blended_length(min_samples=20, cv_sensitivity=2.0) == 100.0
    # Consistent observations at 200 → full confidence → adapts to observation.
    for _ in range(50):
        tracker.observe(200.0)
    assert tracker.blended_length(min_samples=20, cv_sensitivity=2.0) == pytest.approx(200.0, abs=1e-6)


def test_build_trackers_seeds_from_ratios_and_fails_loud_on_missing():
    tree = FabrikTree.from_joint_hierarchy(joint_hierarchy={"a": ["b"]})
    trackers = RealtimeSkeletonFitter._build_trackers(
        tree=tree, bone_length_ratios={"a->b": 0.1}, height_mm=1000.0,
    )
    assert trackers["a->b"].prior == pytest.approx(100.0)
    # Missing / empty / None seeds must raise (no silent fallback).
    with pytest.raises(ValueError):
        RealtimeSkeletonFitter._build_trackers(tree=tree, bone_length_ratios={}, height_mm=1000.0)
    with pytest.raises(ValueError):
        RealtimeSkeletonFitter._build_trackers(tree=tree, bone_length_ratios=None, height_mm=1000.0)


def test_derived_center_bones_are_observed_and_converge_equal():
    # trunk_center is the centroid of shoulders+hips → the exact midpoint of
    # neck_center and hips_center, so these two bones MUST be equal length.
    tree = FabrikTree.from_joint_hierarchy(
        joint_hierarchy={"hips_center": ["trunk_center"], "trunk_center": ["neck_center"]},
    )
    # Deliberately unequal seeds (as in the canonical model: 0.145 vs 0.165).
    trackers = RealtimeSkeletonFitter._build_trackers(
        tree=tree,
        bone_length_ratios={"hips_center->trunk_center": 0.145, "trunk_center->neck_center": 0.165},
        height_mm=1000.0,
    )
    positions = {
        "hips_center": np.array([0.0, 0.0, 0.0]),
        "trunk_center": np.array([0.0, 250.0, 0.0]),
        "neck_center": np.array([0.0, 500.0, 0.0]),
    }
    for _ in range(50):
        RealtimeSkeletonFitter._observe_tree(positions, tree, trackers)

    lower = trackers["hips_center->trunk_center"]
    upper = trackers["trunk_center->neck_center"]
    # Both derived-parent bones are now observed (previously frozen at the seed).
    assert lower.count == 50 and upper.count == 50
    assert lower.mean == pytest.approx(250.0)
    assert upper.mean == pytest.approx(250.0)
    # ...and adapt off their unequal seeds to the equal observed length.
    assert lower.blended_length() == pytest.approx(250.0, abs=1e-6)
    assert upper.blended_length() == pytest.approx(250.0, abs=1e-6)


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
    # The mapping (single center derivation) is loaded.
    assert bio.tracker_mapping is not None

    result = calculate_center_of_mass_per_frame(_upright_rtmpose_pose(), bio)
    com = result.total_body_com
    assert com.shape == (3,)
    assert np.all(np.isfinite(com))
    # CoM sits inside the body's vertical extent (ankles ~80mm, ears ~1700mm).
    assert 80.0 < com[1] < 1700.0
    # Most segments are visible → high-confidence estimate.
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
    for tracker in fitter._body_trackers.values():
        assert tracker.prior > 0.0
