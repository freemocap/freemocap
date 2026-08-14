"""Integration tests for the RealtimeSkeletonRigidifier.

Needs the live skellyforge standard-human model and the skellytracker
RTMPose->standard-human mapping YAMLs in the venv.
"""
import itertools

import numpy as np
import pytest

from skellyforge.skellymodels.standard_human.standard_human_model import (
    compose_standard_human,
)

from freemocap.core.tasks.mocap.rigid_body.skeleton_rigidifier import (
    RealtimeSkeletonRigidifier,
)


# The head's 7 rigid points, in the model's declared order.
_SKULL_POINTS = (
    "head_center",
    "head_vertex",
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
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


def _pairwise_distances(
    positions: dict[str, np.ndarray], names: tuple[str, ...] = _SKULL_POINTS
) -> dict[tuple[str, str], float]:
    """The 21 pairwise distances of the skull, keyed by sorted name tuples."""
    out: dict[tuple[str, str], float] = {}
    for a, b in itertools.combinations(names, 2):
        key = (a, b) if a <= b else (b, a)
        out[key] = float(np.linalg.norm(positions[a] - positions[b]))
    return out


def _frames(
    rig: RealtimeSkeletonRigidifier,
    pose: dict[str, np.ndarray],
    n: int,
    *,
    t0: float = 0.0,
    dt: float = 1.0,
) -> None:
    """Feed ``n`` identical frames so the length windows converge on medians."""
    for i in range(n):
        rig.rigidify_frame(pose, measured=pose, t=t0 + i * dt)


@pytest.fixture
def rigidifier() -> RealtimeSkeletonRigidifier:
    return RealtimeSkeletonRigidifier.create(
        standard_human=compose_standard_human(), height_mm=1750.0
    )


def _frame(rig: RealtimeSkeletonRigidifier, pose: dict[str, np.ndarray], t: float):
    return rig.rigidify_frame(pose, measured=pose, t=t)


def _group_state(rig: RealtimeSkeletonRigidifier, name: str):
    """The per-segment rigid-fit state for ``name`` (e.g. ``"head"``, ``"hips"``)."""
    return rig._rigid_groups[name]  # noqa: SLF001


def _template_distances(
    rig: RealtimeSkeletonRigidifier, name: str
) -> dict[tuple[str, str], float]:
    """The invariant pair distances held by ``name``'s rigid-group template."""
    return _group_state(rig, name).template.pair_distances


def _group_points(name: str) -> tuple[str, ...]:
    """The rigid points of segment ``name`` in model order."""
    return next(
        s.rigid_points
        for s in compose_standard_human().segments
        if s.name == name
    )


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


# ===========================================================================
# Tree edge behavior (unchanged by the skull work) — the two previously-failing
# guarantees must keep passing.
# ===========================================================================


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


# ===========================================================================
# Skull rigid fit — the head is a 7-point rigid body, not an edge.
# ===========================================================================


def test_skull_pairwise_distances_equal_medians(rigidifier):
    # (a) Two frames of the same pose: the corrected head-group's 21 pairwise
    # distances equal the estimated medians EXACTLY — the head is a rigid body.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)
    out = _frame(rig, pose, t=3.0)

    corrected = {name: out.body_positions[name] for name in _SKULL_POINTS}

    corrected_d = _pairwise_distances(corrected)

    # The template holds the pair medians: distances are exact after the fit.
    assert len(corrected_d) == 21
    template_d = _template_distances(rig, "head")
    for key, d in corrected_d.items():
        assert d == pytest.approx(template_d[key], abs=1e-6), key


def test_skull_anchor_is_body_tree_correction(rigidifier):
    # The anchor ``head_center`` is the BODY TREE's corrected head node — the
    # neck chain owns the head's position. In a straight standing pose the
    # corrected head_center is rigidly placed, not the raw mean-of-ears.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)
    out = _frame(rig, pose, t=3.0)

    # head_vertex sits one head-length above head_center (the skull is rigid,
    # and head_center → head_vertex is one of its 21 exact edges).
    head_ratio = next(
        s.length_ratio
        for s in compose_standard_human().segments
        if s.name == "head"
    )
    span = float(np.linalg.norm(
        out.body_positions["head_vertex"] - out.body_positions["head_center"]
    ))
    assert span == pytest.approx(head_ratio * 1750.0, rel=0.1)


def test_articulated_face_points_stay_observed(rigidifier):
    # Jaw / left_mouth / right_mouth are NOT in any rigid set — they anchor at
    # their observed (mapping-output) positions, not displaced by the skull fit.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)
    out = _frame(rig, pose, t=3.0)

    # Re-derive the observed face points from the mapping (same as the wrapper).
    observed = rig._body_mapping.apply(pose)  # noqa: SLF001
    for name in ("jaw", "left_mouth", "right_mouth"):
        assert name in out.body_positions, name
        assert np.allclose(out.body_positions[name], observed[name], atol=1e-6), name


def test_orphan_anchor_emits_approximate_axis_keypoints(rigidifier):
    # The foot/toes segments' approximate (twist) axis keypoints — left_heel /
    # right_heel (foot twist) and left_small_toe / right_small_toe (toes twist) —
    # are not the segment origin or long-axis endpoint, so the tree leaves them
    # out. The orphan-anchor rule must still emit them at their observed
    # positions, or those segments silently lose their twist direction every
    # frame and fall to the damped fallback.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)
    out = _frame(rig, pose, t=3.0)

    observed = rig._body_mapping.apply(pose)  # noqa: SLF001
    for name in ("left_heel", "right_heel", "left_small_toe", "right_small_toe"):
        assert name in out.body_positions, name
        assert np.allclose(out.body_positions[name], observed[name], atol=1e-6), name


def test_noise_on_one_skull_point_keeps_skull_rigid(rigidifier):
    # (b) Large noise on ONE skull point (nose) for one frame: the corrected
    # skull stays rigid (all 21 pairwise distances still exact) and the corrected
    # nose is the template-extrapolated position, not the noisy observation.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)
    clean = _frame(rig, pose, t=3.0)
    clean_d = _pairwise_distances(
        {n: clean.body_positions[n] for n in _SKULL_POINTS}
    )

    noisy = dict(pose)
    noisy["nose"] = np.array([200.0, 500.0, 300.0])  # wildly wrong nose
    out = _frame(rig, noisy, t=4.0)

    corrected_d = _pairwise_distances(
        {n: out.body_positions[n] for n in _SKULL_POINTS}
    )
    # Rigid: every pairwise distance unchanged (the fit is a rigid transform).
    for key in clean_d:
        assert corrected_d[key] == pytest.approx(clean_d[key], abs=1e-6), key

    # The corrected nose is the template geometry, NOT the noisy observation.
    assert not np.allclose(out.body_positions["nose"], noisy["nose"], atol=10.0)
    assert np.linalg.norm(out.body_positions["nose"] - noisy["nose"]) > 100.0
    assert np.linalg.norm(out.body_positions["nose"] - clean.body_positions["nose"]) < 5.0


def test_missing_skull_point_extrapolated(rigidifier):
    # (c) A frame with ``left_ear`` missing: the fit still emits a corrected
    # ``left_ear`` (extrapolated from the template — the point of a rigid body).
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)
    missing = dict(pose)
    del missing["left_ear"]
    out = _frame(rig, missing, t=3.0)

    assert "left_ear" in out.body_positions
    left_ear = out.body_positions["left_ear"]
    assert np.all(np.isfinite(left_ear))


def test_fewer_than_three_skull_points_passthrough(rigidifier):
    # (d) Fewer than 3 skull points observed: the fit is under-determined and
    # passes observed through (corrected == observed for the surviving skull
    # points, no crash).
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)

    few = dict(pose)
    # Leave only ``nose`` as a skull rigid point (+ head_center derived from the
    # ears the rest of the pose still carries); drop both eyes and both ears so
    # fewer than 3 of the 7 rigid points remain observed.
    for name in ("left_eye", "right_eye", "left_ear", "right_ear"):
        few.pop(name, None)
    out = _frame(rig, few, t=3.0)

    # No crash; nose (the one surviving rigid point) is present at observed.
    assert "nose" in out.body_positions
    assert np.allclose(out.body_positions["nose"], pose["nose"], atol=1e-6)


def test_skull_template_rebuild_is_chirality_stable(rigidifier):
    # Feed 31+ frames (t = 0..30) so the 30-frame template REBUILD fires at least
    # once. The head-group must remain rigid (pairwise distances == estimator
    # medians) AND chirality-consistent across the rebuild: the corrected ``nose``
    # stays on the same side of the eye/ear plane, and nothing crashes.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    n = 31
    for i in range(n):
        _frame(rig, pose, t=float(i))

    # Sanity: the rebuild actually fired at least twice (template built at frame
    # 0 and rebuilt at frame 30).
    assert _group_state(rig, "head").frames_since_template_build < 30

    template_d = _template_distances(rig, "head")

    # Chirality reference: a plane through left_ear/right_ear/left_eye (three
    # observed skull points). The corrected ``nose`` must stay on the SAME side
    # of that plane every frame.
    le = pose["left_ear"]
    re = pose["right_ear"]
    third = pose["left_eye"]
    plane_normal = np.cross(re - le, third - le)
    plane_normal = plane_normal / np.linalg.norm(plane_normal)

    sign_ref = None
    for i in range(n):
        out = _frame(rig, pose, t=float(n + i))  # post-rebuild steady-state frames
        corrected = {name: out.body_positions[name] for name in _SKULL_POINTS}
        corrected_d = _pairwise_distances(corrected)
        for key, d in corrected_d.items():
            assert d == pytest.approx(template_d[key], abs=1e-6), key

        nose = out.body_positions["nose"]
        s = float(np.sign(np.dot(nose - le, plane_normal)))
        assert s != 0.0
        if sign_ref is None:
            sign_ref = s
        assert s == sign_ref, f"chirality flipped at frame {i}"


# ===========================================================================
# Per-group rigid fit — every ≥ 3-rigid-point segment is a rigid body fit
# (head, hips, both feet, both toes), keyed by segment name.
# ===========================================================================


def _group_pairwise(
    out: "object", names: tuple[str, ...]
) -> dict[tuple[str, str], float]:
    """The pairwise distances of the output positions ``out.body_positions``."""
    positions = {name: out.body_positions[name] for name in names}
    return _pairwise_distances(positions, names)


def test_foot_group_keeps_pairwise_distances_exact_under_heel_noise(rigidifier):
    # The left foot is a 3-point rigid group (``left_ankle``, ``left_foot_ball``,
    # ``left_heel``). Noise on ONE point (``left_heel``) → the corrected heel is
    # template-extrapolated, and all 3 pairwise distances stay exact.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)
    clean = _frame(rig, pose, t=3.0)
    clean_d = _group_pairwise(clean, _group_points("left_foot"))

    noisy = dict(pose)
    noisy["left_heel"] = pose["left_heel"] + np.array([80.0, -50.0, 120.0])
    out = _frame(rig, noisy, t=4.0)

    corrected_d = _group_pairwise(out, _group_points("left_foot"))
    for key in clean_d:
        assert corrected_d[key] == pytest.approx(clean_d[key], abs=1e-6), key

    # The corrected heel is the template geometry, not the noisy observation.
    assert not np.allclose(out.body_positions["left_heel"], noisy["left_heel"], atol=10.0)


def test_hips_group_keeps_pairwise_distances_exact_under_hip_noise(rigidifier):
    # The hips is a 4-point rigid group (a tree root, anchored at the observed
    # ``hips_center``). Noise on ONE point (``left_hip``) → the corrected hip is
    # template-extrapolated, and all 6 pairwise distances stay exact.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)
    clean = _frame(rig, pose, t=3.0)
    clean_d = _group_pairwise(clean, _group_points("hips"))

    noisy = dict(pose)
    noisy["left_hip"] = pose["left_hip"] + np.array([60.0, -40.0, 90.0])
    out = _frame(rig, noisy, t=4.0)

    corrected_d = _group_pairwise(out, _group_points("hips"))
    for key in clean_d:
        assert corrected_d[key] == pytest.approx(clean_d[key], abs=1e-6), key


def test_hips_anchor_is_observed_center(rigidifier):
    # The hips is a tree root: its origin ``hips_center`` anchors at its observed
    # (mapping-derived) position, not displaced by the tree or the fit.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)
    out = _frame(rig, pose, t=3.0)
    observed = rig._body_mapping.apply(pose)  # noqa: SLF001
    assert np.allclose(out.body_positions["hips_center"], observed["hips_center"], atol=1e-6)


def test_toes_group_keeps_pairwise_distances_exact(rigidifier):
    # The left toes is a 3-point rigid group (``left_foot_ball``, ``left_big_toe``,
    # ``left_small_toe``). Its pairwise distances stay exact after the fit.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)
    out = _frame(rig, pose, t=3.0)

    names = _group_points("left_toes")
    template_d = _template_distances(rig, "left_toes")
    corrected_d = _group_pairwise(out, names)
    for key in template_d:
        assert corrected_d[key] == pytest.approx(template_d[key], abs=1e-6), key


def test_missing_rigid_point_still_extrapolated_and_rigid(rigidifier):
    # Drop one hip (a 4-point group's rigid point). The fit still emits the
    # missing point (extrapolated from the template — a rigid group holds every
    # point), and every pairwise distance stays at the template's exactly.
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)

    names = _group_points("hips")
    missing = dict(pose)
    del missing["left_hip"]
    out = _frame(rig, missing, t=4.0)

    assert "left_hip" in out.body_positions
    assert np.all(np.isfinite(out.body_positions["left_hip"]))

    template_d = _template_distances(rig, "hips")
    corrected_d = _group_pairwise(out, names)
    for key in template_d:
        assert corrected_d[key] == pytest.approx(template_d[key], abs=1e-6), key


def test_fewer_than_three_foot_points_passthrough(rigidifier):
    # Fewer than 3 of the foot's rigid points observed → the fit is under-
    # determined and passes the observed points through (no crash).
    rig = rigidifier
    pose = _upright_rtmpose_pose()
    _frames(rig, pose, n=3)

    few = dict(pose)
    # ``left_heel`` is a rigid point; ``left_big_toe`` feeds the derived
    # ``left_foot_ball``, so removing both leaves only ``left_ankle`` observed.
    del few["left_heel"]
    del few["left_big_toe"]
    out = _frame(rig, few, t=3.0)

    # Anchored point is present and the fit is under-determined (no crash,
    # finite output).
    assert "left_ankle" in out.body_positions
    assert np.all(np.isfinite(out.body_positions["left_ankle"]))


def test_two_point_segment_still_enforces_span_exactly(rigidifier):
    # A 2-point segment (``left_upper_arm``) has no rigid-group fit; its span is
    # enforced exactly by the tree forward pass — no template, no rotation fit.
    rig = rigidifier
    # Make sure the 2-point segment is NOT in the rigid-group map.
    assert "left_upper_arm" not in rig._rigid_groups  # noqa: SLF001

    pose = _upright_rtmpose_pose()
    _frame(rig, pose, t=0.0)
    est = rig.body_segment_lengths["left_upper_arm"]
    out = _frame(rig, pose, t=0.1)
    body = out.body_positions
    measured = float(np.linalg.norm(body["left_elbow"] - body["left_shoulder"]))
    assert measured == pytest.approx(est, abs=1e-6)
