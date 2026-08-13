"""Center-of-mass tests on the de Leva (1996) body-segment inertial parameters.

Covers both entry points: from raw RTMPose tracker keypoints
(``calculate_center_of_mass_per_frame``) and from already-canonical positions
(``calculate_center_of_mass_from_canonical`` — the path used by the rigidified
skeleton, matching the posthoc ``rigid_xyz -> CoM`` flow).
"""
import numpy as np
import pytest

from freemocap.core.tasks.mocap.center_of_mass import (
    CoMConfidence,
    calculate_center_of_mass_from_canonical,
    calculate_center_of_mass_per_frame,
    load_body_biomechanics,
)
from skellyforge.kinematics.inertial.anthropometric_parameters import (
    segment_inertial_parameters,
)


def _v(x, y, z):
    return np.array([float(x), float(y), float(z)])


def _upright_rtmpose_pose() -> dict[str, np.ndarray]:
    """A crude upright standing pose in mm (RTMPose body keypoint names).

    Names must include the surface keypoints the mapping needs to derive the
    off-surface span endpoints (mid_sternum, head_vertex, foot_ball): the ears
    (for head_center), nose/eyes (for the head frame), and the toes/heel (for
    foot_ball).
    """
    return {
        "nose": _v(0, 1580, 0),
        "left_eye": _v(-30, 1620, 60), "right_eye": _v(30, 1620, 60),
        "left_ear": _v(-70, 1600, 0), "right_ear": _v(70, 1600, 0),
        "left_shoulder": _v(-200, 1450, 0), "right_shoulder": _v(200, 1450, 0),
        "left_elbow": _v(-220, 1150, 0), "right_elbow": _v(220, 1150, 0),
        "left_wrist": _v(-230, 900, 0), "right_wrist": _v(230, 900, 0),
        "left_hip": _v(-120, 950, 0), "right_hip": _v(120, 950, 0),
        "left_knee": _v(-130, 500, 0), "right_knee": _v(130, 500, 0),
        "left_ankle": _v(-140, 80, 0), "right_ankle": _v(140, 80, 0),
        "left_heel": _v(-140, 20, -80), "right_heel": _v(140, 20, -80),
        "left_big_toe": _v(-140, 20, 150), "right_big_toe": _v(140, 20, 150),
        "left_small_toe": _v(-140, 20, 80), "right_small_toe": _v(140, 20, 80),
    }


def test_center_of_mass_uses_de_leva_biomechanics():
    bio = load_body_biomechanics()
    assert bio.tracker_mapping is not None
    assert set(bio.de_leva.keys()) == {
        "head", "trunk", "upper_arm", "forearm",
        "hand", "thigh", "shank", "foot",
    }

    result = calculate_center_of_mass_per_frame(_upright_rtmpose_pose(), bio)
    com = result.total_body_com
    assert com.shape == (3,)
    assert np.all(np.isfinite(com))
    assert 80.0 < com[1] < 1700.0
    assert result.confidence >= CoMConfidence.medium


def test_com_from_canonical_matches_tracker_path():
    # The refactor must be behaviour-preserving: feeding canonical positions
    # directly equals mapping tracker keypoints then computing CoM.
    bio = load_body_biomechanics()
    pose = _upright_rtmpose_pose()

    via_tracker = calculate_center_of_mass_per_frame(pose, bio)
    canonical = bio.tracker_mapping.apply(pose)
    via_canonical = calculate_center_of_mass_from_canonical(canonical, bio)

    assert np.allclose(via_tracker.total_body_com, via_canonical.total_body_com)
    assert via_canonical.confidence == via_tracker.confidence


def test_de_leva_mean_masses_sum_to_one():
    # de Leva Table 4 reports per-side mass fractions for the six paired
    # limbs; the whole body sums to ~1.0 only with each limb counted twice
    # (as the redistribution does, via its bilateral span expansion).
    de_leva = segment_inertial_parameters("mean")
    midline = ("head", "trunk")
    limbs = ("upper_arm", "forearm", "hand", "thigh", "shank", "foot")
    total = sum(de_leva[m].mass_fraction for m in midline) + sum(
        de_leva[l].mass_fraction for l in limbs
    ) * 2
    assert total == pytest.approx(1.0, abs=1e-3)


def test_thigh_com_is_com_fraction_along_the_segment():
    # Pin a known de Leva value: the thigh CoM sits at com_fraction along the
    # hip → knee span. From a synthetic straight standing pose (both legs
    # vertical), thigh com_fraction is measured from the proximal hip end.
    bio = load_body_biomechanics()
    canonical = bio.tracker_mapping.apply(_upright_rtmpose_pose())

    com_fraction = bio.de_leva["thigh"].com_fraction
    hip = canonical["left_hip"]
    knee = canonical["left_knee"]

    result = calculate_center_of_mass_from_canonical(canonical, bio)
    assert "left_thigh" in result.segment_coms
    expected = hip + (knee - hip) * com_fraction
    assert np.allclose(result.segment_coms["left_thigh"], expected)
