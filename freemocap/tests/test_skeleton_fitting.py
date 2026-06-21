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
    _BoneLengthCorrector,
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


# ---------------------------------------------------------------------------
# Integral bone-length corrector
# ---------------------------------------------------------------------------


def test_corrector_starts_at_zero():
    """A fresh corrector has zero integral → zero correction."""
    c = _BoneLengthCorrector()
    assert c.integral == 0.0
    assert c.get_correction(max_correction_mm=50.0) == 0.0


def test_corrector_accumulates_positive_residual():
    """Persistent positive axial error → positive integral → positive correction."""
    c = _BoneLengthCorrector()
    leak = 0.90
    ki = 0.10
    # Feed a constant +10 mm axial residual (bone consistently too short).
    # With the true integrator: integral = leak*integral + ki*error
    # Steady state: integral = ki*error / (1-leak) = 0.10*10 / 0.10 = 10.0
    for _ in range(60):
        c.update(axial_error_mm=10.0, leak=leak, ki=ki)
    assert c.integral == pytest.approx(10.0, abs=0.05)
    correction = c.get_correction(max_correction_mm=50.0)
    assert correction == pytest.approx(10.0, abs=0.05)


def test_corrector_accumulates_negative_residual():
    """Persistent negative axial error → negative integral → negative correction."""
    c = _BoneLengthCorrector()
    leak = 0.90
    ki = 0.10
    for _ in range(60):
        c.update(axial_error_mm=-8.0, leak=leak, ki=ki)
    # Steady state: 0.10 * (-8) / 0.10 = -8.0
    assert c.integral == pytest.approx(-8.0, abs=0.05)
    correction = c.get_correction(max_correction_mm=50.0)
    assert correction == pytest.approx(-8.0, abs=0.05)


def test_corrector_decays_to_zero():
    """When residuals stop, the integrator decays toward zero."""
    c = _BoneLengthCorrector()
    leak = 0.90
    ki = 0.10
    # Build up some error first
    for _ in range(60):
        c.update(axial_error_mm=10.0, leak=leak, ki=ki)
    assert c.integral > 5.0  # built up significant integral
    # Now feed zero residuals — integral should decay
    for _ in range(50):
        c.update(axial_error_mm=0.0, leak=leak, ki=ki)
    # After 50 frames of zero: integral ≈ 10 * 0.90^50 ≈ 0.05
    assert c.integral == pytest.approx(0.0, abs=0.1)


def test_corrector_clamps_at_limit():
    """get_correction clamps the output to ±max_correction_mm."""
    c = _BoneLengthCorrector()
    c.integral = 2000.0
    correction = c.get_correction(max_correction_mm=30.0)
    assert correction == 30.0  # clamped
    c.integral = -2000.0
    correction = c.get_correction(max_correction_mm=30.0)
    assert correction == -30.0


def test_corrector_ki_scales_accumulation():
    """Higher ki → faster accumulation for the same error."""
    c_low = _BoneLengthCorrector()
    c_high = _BoneLengthCorrector()
    leak = 0.95
    for _ in range(30):
        c_low.update(axial_error_mm=10.0, leak=leak, ki=0.05)
        c_high.update(axial_error_mm=10.0, leak=leak, ki=0.20)
    assert c_high.integral > c_low.integral


def test_corrector_leak_controls_memory():
    """Higher leak (closer to 1) → longer memory, more accumulation."""
    c_slow = _BoneLengthCorrector()
    c_fast = _BoneLengthCorrector()
    ki = 0.10
    # Feed both one frame of +10 error
    c_slow.update(axial_error_mm=10.0, leak=0.95, ki=ki)  # slow decay
    c_fast.update(axial_error_mm=10.0, leak=0.80, ki=ki)  # fast decay
    assert c_slow.integral == pytest.approx(1.0)   # 0.10*10 = 1.0
    assert c_fast.integral == pytest.approx(1.0)   # same first frame
    # Feed many frames of zero; fast-decay corrector forgets quicker
    for _ in range(20):
        c_slow.update(axial_error_mm=0.0, leak=0.95, ki=ki)
        c_fast.update(axial_error_mm=0.0, leak=0.80, ki=ki)
    assert c_fast.integral < c_slow.integral


# ---------------------------------------------------------------------------
# Integral correction + FABRIK end-to-end
# ---------------------------------------------------------------------------


def test_integral_correction_helps_fabrik_recover_from_wrong_bone_length():
    """When bone length is too long, the integral corrector detects the
    persistent axial residual and biases the bone shorter, allowing FABRIK
    to place joints closer to their tracker targets."""
    tree = FabrikTree.from_joint_hierarchy(
        joint_hierarchy={"hip": ["knee"], "knee": ["ankle"]},
    )
    # True bone lengths
    true_lengths = {"hip->knee": 400.0, "knee->ankle": 380.0}

    # Generate a "correct" target pose: colinear, matching true lengths
    hip_target = np.array([0.0, 0.0, 0.0])
    knee_target = np.array([0.0, 400.0, 0.0])   # 400 mm below hip
    ankle_target = np.array([0.0, 780.0, 0.0])  # 380 mm below knee
    targets = {"hip": hip_target, "knee": knee_target, "ankle": ankle_target}

    # Sanity: FABRIK with correct lengths places joints at targets
    solved_good = solve_fabrik_tree(
        targets=targets, tree=tree, bone_lengths=true_lengths,
        tolerance=0.1, max_iterations=20,
    )
    for name in targets:
        assert np.allclose(solved_good[name], targets[name], atol=1e-4)

    # Now simulate wrong bone lengths: femur 30% too long
    wrong_lengths = {"hip->knee": 520.0, "knee->ankle": 380.0}
    solved_bad = solve_fabrik_tree(
        targets=targets, tree=tree, bone_lengths=wrong_lengths,
        tolerance=0.1, max_iterations=20,
    )
    knee_error_bad = float(np.linalg.norm(solved_bad["knee"] - knee_target))
    assert knee_error_bad > 1.0  # significant error with wrong lengths

    # Simulate per-frame correction: run FABRIK, measure residual, update
    # corrector, apply correction, repeat.
    #
    # With a leaky integrator (leak < 1), the steady-state correction is:
    #     correction_ss = ki * (true - wrong) / (1 - leak + ki)
    # and the remaining error is:
    #     error_ss = (true - wrong) * (1 - leak) / (1 - leak + ki)
    #
    # For wrong=520, true=400, ki=0.15, leak=0.95:
    #     correction_ss = 0.15*(-120)/(0.05+0.15) = -90 mm
    #     error_ss = -120 * 0.05 / 0.20 = -30 mm  → |error| = 30 mm
    # So the femur converges from 520 → 430 and error from 120 → 30.
    correctors = {bk: _BoneLengthCorrector() for bk in tree.bone_keys}
    ki = 0.15
    leak = 0.95
    max_correction = 130.0  # allow enough correction range for this extreme case

    effective_lengths = dict(wrong_lengths)
    knee_errors = [knee_error_bad]

    for _frame in range(80):
        solved = solve_fabrik_tree(
            targets=targets, tree=tree, bone_lengths=effective_lengths,
            tolerance=0.1, max_iterations=20,
        )
        knee_errors.append(float(np.linalg.norm(solved["knee"] - knee_target)))

        # Compute axial residuals and update correctors
        for bone_key in tree.bone_keys:
            parent_name, child_name = bone_key.split("->", 1)
            solved_parent = solved[parent_name]
            solved_child = solved[child_name]
            target_child = targets[child_name]
            bone_vec = solved_child - solved_parent
            bone_dist = float(np.linalg.norm(bone_vec))
            if bone_dist < 1e-9:
                continue
            bone_dir = bone_vec / bone_dist
            residual = target_child - solved_child
            axial_error = float(np.dot(residual, bone_dir))
            correctors[bone_key].update(
                axial_error_mm=axial_error, leak=leak, ki=ki,
            )

        # Apply correction for next frame
        for bk in tree.bone_keys:
            correction = correctors[bk].get_correction(max_correction)
            effective_lengths[bk] = wrong_lengths[bk] + correction

    # The knee error should decrease substantially — from 120mm toward ~30mm
    # (the steady-state error of a leaky integrator with these gains).
    assert knee_errors[-1] < knee_errors[0] * 0.35, (
        f"Integral correction should reduce knee error substantially; "
        f"initial={knee_errors[0]:.1f}mm, final={knee_errors[-1]:.1f}mm"
    )

    # The effective femur length should have been pulled toward the true value
    final_femur = effective_lengths["hip->knee"]
    assert final_femur < wrong_lengths["hip->knee"], (
        f"Integral should have shortened the femur; "
        f"wrong={wrong_lengths['hip->knee']:.0f}, effective={final_femur:.0f}"
    )
    # After 80 frames with leak=0.95, ki=0.15, the femur should converge
    # to roughly 430 mm (520 - 90).  Within ±15mm of that steady state.
    expected_ss = wrong_lengths["hip->knee"] + ki * (true_lengths["hip->knee"] - wrong_lengths["hip->knee"]) / (1.0 - leak + ki)
    assert final_femur == pytest.approx(expected_ss, abs=15.0), (
        f"Femur should converge toward steady state {expected_ss:.0f}mm; "
        f"got {final_femur:.0f}mm"
    )


# ---------------------------------------------------------------------------
# Welford capped samples (staleness prevention)
# ---------------------------------------------------------------------------


def test_welford_capped_samples_stays_responsive():
    """After max_effective_samples, the estimator uses constant-weight EMA
    so new data can still shift the mean — unlike cumulative Welford where
    1/count → 0 and the mean freezes."""
    tracker = _WelfordTracker(prior=100.0)
    cap = 50

    # Burn in: establish a mean of 200.0
    for _ in range(100):
        tracker.observe(200.0, max_effective_samples=cap)

    # After 100 frames of 200, cumulative mean would be ~200 and nearly frozen.
    # With capped EMA, 50 more frames of 150 should pull the mean down.
    for _ in range(50):
        tracker.observe(150.0, max_effective_samples=cap)

    # A cumulative (uncapped) Welford would still be ~197 after this.
    # The capped version should have moved substantially toward 150.
    assert tracker.mean < 185.0, (
        f"Capped Welford should adapt to new data; got mean={tracker.mean:.1f}"
    )


def test_welford_capped_vs_uncapped_divergence():
    """Capped and uncapped estimators should diverge after many frames."""
    capped = _WelfordTracker(prior=100.0)
    uncapped = _WelfordTracker(prior=100.0)
    cap = 30

    # Seed both with 200mm for 200 frames
    for _ in range(200):
        capped.observe(200.0, max_effective_samples=cap)
        uncapped.observe(200.0, max_effective_samples=999_999_999)

    # Both should be near 200
    assert capped.mean == pytest.approx(200.0, abs=1.0)
    assert uncapped.mean == pytest.approx(200.0, abs=1.0)

    # Now feed 100 frames of 300mm
    for _ in range(100):
        capped.observe(300.0, max_effective_samples=cap)
        uncapped.observe(300.0, max_effective_samples=999_999_999)

    # Capped should have moved substantially toward 300
    # Uncapped should have barely moved (100 frames out of 300 total)
    assert capped.mean > 250.0, (
        f"Capped should move toward 300; got {capped.mean:.1f}"
    )
    assert uncapped.mean < 240.0, (
        f"Uncapped should barely budge from 200; got {uncapped.mean:.1f}"
    )


# ---------------------------------------------------------------------------
# Within-frame FABRIK refinement (escapes coupled-bone local minima)
# ---------------------------------------------------------------------------


def test_refinement_reduces_residual_for_wrong_bone_lengths():
    """With wrong bone lengths, within-frame refinement should find a
    solution with lower total joint error than the primary solve alone."""
    from freemocap.core.tasks.mocap.realtime_skeleton_fitter import (
        _compute_axial_residuals_dict,
        _compute_total_residual,
    )

    tree = FabrikTree.from_joint_hierarchy(
        joint_hierarchy={"hip": ["knee"], "knee": ["ankle"]},
    )
    # Targets at correct lengths (400, 380)
    targets = {
        "hip": np.array([0.0, 0.0, 0.0]),
        "knee": np.array([0.0, 400.0, 0.0]),
        "ankle": np.array([0.0, 780.0, 0.0]),
    }
    # Wrong femur length (520 instead of 400)
    bone_lengths = {"hip->knee": 520.0, "knee->ankle": 380.0}

    # Primary solve
    primary = solve_fabrik_tree(
        targets=targets, tree=tree, bone_lengths=bone_lengths,
        tolerance=0.1, max_iterations=20,
    )
    primary_error = _compute_total_residual(primary, targets)
    assert primary_error > 100.0  # significant error as expected

    # One refinement pass: nudge bone lengths based on residuals
    residuals = _compute_axial_residuals_dict(
        solved=primary, targets=targets, tree=tree,
    )
    refined_lengths = dict(bone_lengths)
    gain = 0.3
    for bk, length in bone_lengths.items():
        axial = residuals.get(bk, 0.0)
        refined_lengths[bk] = length + gain * axial
        if refined_lengths[bk] < 5.0:
            refined_lengths[bk] = 5.0

    refined = solve_fabrik_tree(
        targets=targets, tree=tree, bone_lengths=refined_lengths,
        tolerance=0.1, max_iterations=20,
    )
    refined_error = _compute_total_residual(refined, targets)

    # Refinement should reduce error
    assert refined_error < primary_error, (
        f"Refinement should reduce error; "
        f"primary={primary_error:.1f}mm, refined={refined_error:.1f}mm"
    )


def test_refinement_helps_coupled_branch_bones():
    """A Y-split (like ankle → heel + toes) creates coupled constraints.
    Refinement should help escape the compromise equilibrium."""
    from freemocap.core.tasks.mocap.realtime_skeleton_fitter import (
        _compute_axial_residuals_dict,
        _compute_total_residual,
    )

    # Ankle splits to three foot points (like the real body model)
    tree = FabrikTree.from_joint_hierarchy(
        joint_hierarchy={
            "knee": ["ankle"],
            "ankle": ["heel", "big_toe", "small_toe"],
        },
    )
    targets = {
        "knee": np.array([0.0, 500.0, 0.0]),
        "ankle": np.array([0.0, 900.0, 0.0]),
        "heel": np.array([-30.0, 950.0, 0.0]),
        "big_toe": np.array([20.0, 1000.0, 50.0]),
        "small_toe": np.array([40.0, 990.0, -30.0]),
    }
    # Deliberately wrong bone lengths
    bone_lengths = {
        "knee->ankle": 450.0,     # true is 400
        "ankle->heel": 60.0,      # true is ~58
        "ankle->big_toe": 120.0,  # true is ~102
        "ankle->small_toe": 110.0, # true is ~96
    }

    primary = solve_fabrik_tree(
        targets=targets, tree=tree, bone_lengths=bone_lengths,
        tolerance=0.1, max_iterations=20,
    )
    primary_error = _compute_total_residual(primary, targets)

    # Run 3 refinement passes (2 deterministic + 1 jittered)
    rng = np.random.default_rng(42)
    best_solution = primary
    best_error = primary_error
    best_lengths = dict(bone_lengths)
    gain = 0.3
    jitter = 3.0

    for pass_idx in range(3):
        residuals = _compute_axial_residuals_dict(
            solved=best_solution, targets=targets, tree=tree,
        )
        candidate_lengths = {}
        for bk, length in best_lengths.items():
            axial = residuals.get(bk, 0.0)
            noise = rng.normal(0.0, jitter) if pass_idx == 2 else 0.0
            candidate_lengths[bk] = length + gain * axial + noise
            if candidate_lengths[bk] < 5.0:
                candidate_lengths[bk] = 5.0

        candidate = solve_fabrik_tree(
            targets=targets, tree=tree, bone_lengths=candidate_lengths,
            tolerance=0.1, max_iterations=20,
        )
        candidate_error = _compute_total_residual(candidate, targets)

        if candidate_error < best_error:
            best_solution = candidate
            best_error = candidate_error
            best_lengths = candidate_lengths

    # Refinement should find a better or equal solution
    assert best_error <= primary_error, (
        f"Refinement should not worsen error; "
        f"primary={primary_error:.1f}mm, best={best_error:.1f}mm"
    )
