"""The body-scale fit through the real loop: tracker keypoints -> mapping -> fit.

The unit tests for the fit live in skellyforge and drive it from the rest pose. This one
drives it the way the aggregator does — synthetic rtmpose keypoints through the REAL
tracker mapping — because two of the things that have to be right are only visible here:

* which landmarks the mapping MEASURES rather than constructs from authored ratios, and
  therefore which segments are allowed to set the subject's height;
* that a subject seen from the waist up still gets a whole, correctly-sized skeleton.

The second is the case the proportional template exists for, and it is the ordinary case:
somebody sitting at a desk has no visible knees, ankles or feet.
"""
from __future__ import annotations

import numpy as np
import pytest

from freemocap.core.tasks.mocap.tracker_mappings import load_standard_human_mapping
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.model_scale_fitting import (
    ModelScaleFit,
    StreamingModelScaleFitter,
    scale_voting_segment_names,
)
from skellyforge.core.skeleton.pose.hydration import hydrate_skeleton
from skellyforge.core.skeleton.pose.roll_resolution import ContinuousRollResolver
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition

# Everything a desk hides. The hips stay visible — this is somebody at a keyboard, not
# somebody cut off at the waist.
_BELOW_THE_DESK = ("knee", "ankle", "toe", "heel")

# A real adult, loosely. The synthetic subject below is not the template's proportions, so
# the fit lands near but not on the height its nose implies — which is the point of asking
# for a plausible range rather than an exact number.
_PLAUSIBLE_HEIGHT_RANGE_MM = (1400.0, 2100.0)


def _standing_keypoints() -> dict[str, np.ndarray]:
    """A standing rtmpose-named pose in the Blender convention, in millimetres."""

    def p(x: float, y: float, z: float) -> np.ndarray:
        return np.array([float(x), float(y), float(z)])

    return {
        "nose": p(0.0, 0.0, 1720.0),
        "left_eye": p(-30.0, 0.0, 1730.0),
        "right_eye": p(30.0, 0.0, 1730.0),
        "left_ear": p(-60.0, 0.0, 1700.0),
        "right_ear": p(60.0, 0.0, 1700.0),
        "left_shoulder": p(-200.0, 0.0, 1450.0),
        "right_shoulder": p(200.0, 0.0, 1450.0),
        "left_elbow": p(-220.0, 0.0, 1150.0),
        "right_elbow": p(220.0, 0.0, 1150.0),
        "left_wrist": p(-230.0, 0.0, 900.0),
        "right_wrist": p(230.0, 0.0, 900.0),
        "left_hip": p(-120.0, 0.0, 950.0),
        "right_hip": p(120.0, 0.0, 950.0),
        "left_knee": p(-130.0, 0.0, 500.0),
        "right_knee": p(130.0, 0.0, 500.0),
        "left_ankle": p(-140.0, 0.0, 80.0),
        "right_ankle": p(140.0, 0.0, 80.0),
        "left_big_toe": p(-140.0, 150.0, 20.0),
        "right_big_toe": p(140.0, 150.0, 20.0),
        "left_small_toe": p(-160.0, 140.0, 20.0),
        "right_small_toe": p(160.0, 140.0, 20.0),
        "left_heel": p(-140.0, -40.0, 40.0),
        "right_heel": p(140.0, -40.0, 40.0),
    }


def _seated_keypoints() -> dict[str, np.ndarray]:
    return {
        name: position
        for name, position in _standing_keypoints().items()
        if not any(hidden in name for hidden in _BELOW_THE_DESK)
    }


def _skeleton_and_voting_segments() -> tuple[SkeletonDefinition, frozenset[str]]:
    skeleton = SkeletonDefinition.from_default_yaml()
    mapping = load_standard_human_mapping("rtmpose")
    return skeleton, scale_voting_segment_names(
        skeleton=skeleton,
        measured_landmark_names=mapping.directly_measured_landmark_names,
    )


def _fit(keypoints: dict[str, np.ndarray]) -> ModelScaleFit:
    """The aggregator's per-frame order: map -> hydrate -> resolve roll -> fit."""
    skeleton, voting = _skeleton_and_voting_segments()
    mapping = load_standard_human_mapping("rtmpose")
    observed = {
        name: Point.from_array(values=position)
        for name, position in mapping.apply(tracker_positions=keypoints).items()
    }
    resolved = ContinuousRollResolver.for_skeleton(skeleton=skeleton).resolve_pose(
        pose=hydrate_skeleton(skeleton=skeleton, observed=observed, require_all=False)
    )
    fitter = StreamingModelScaleFitter(skeleton=skeleton, voting_segment_names=voting)
    fitter.observe_pose(pose=resolved)
    return fitter.current_fit()


def test_only_measured_landmarks_earn_a_vote_on_the_subjects_height() -> None:
    """The mapping's constructed landmarks must not vote on how big the subject is."""
    skeleton, voting = _skeleton_and_voting_segments()

    # The long limb bones, which is what actually measures a person.
    for name in (
        "left_upper_leg",
        "right_upper_leg",
        "left_lower_leg",
        "right_lower_leg",
        "left_upper_arm",
        "right_upper_arm",
        "left_lower_arm",
        "right_lower_arm",
    ):
        assert name in voting, f"{name} is measured end to end and should vote"

    # The trunk is built from anatomical offsets — authored ratios of a measured span —
    # so it restates the template rather than measuring the subject.
    for name in ("sacrolumbar", "thoracic", "cervical_spine", "left_clavicle"):
        assert name not in voting, f"{name} is constructed from ratios and must not vote"

    # The pelvis, thorax and skull rigid-fit over landmark sets that include constructed
    # points, so all three are excluded — deliberately strict.
    for name in ("pelvis", "thoracic", "skull"):
        assert name not in voting

    assert voting < frozenset(skeleton.segments), "not every segment can vote"


def test_a_standing_subject_fits_a_plausible_body() -> None:
    fit = _fit(_standing_keypoints())

    low, high = _PLAUSIBLE_HEIGHT_RANGE_MM
    assert low < fit.fitted_scale < high, f"fitted {fit.fitted_scale:.0f}mm"
    # Every segment of the standard human has a length, in millimetres.
    skeleton, _ = _skeleton_and_voting_segments()
    assert set(fit.segment_lengths) == set(skeleton.segments)
    assert all(length > 0.0 for length in fit.segment_lengths.values())
    # And they are anatomy, not template units: a femur is a few hundred millimetres.
    assert 350.0 < fit.segment_lengths["left_upper_leg"] < 550.0


def test_a_subject_at_a_desk_still_gets_correctly_sized_feet() -> None:
    """The whole point. No knees, no ankles, no feet — and the feet still come out right.

    Nothing here measures a floor or assumes the subject is standing. The height is pooled
    from the arms alone, and the invisible foot is sized from it.
    """
    standing = _fit(_standing_keypoints())
    seated = _fit(_seated_keypoints())

    # The desk really did take the legs away.
    assert "left_lower_leg" not in seated.measured_segment_names
    assert "left_foot" not in seated.measured_segment_names
    assert len(seated.voting_segment_names) < len(standing.voting_segment_names)
    assert seated.voting_segment_names, "the arms must still be measuring the subject"

    # The height barely moves...
    assert seated.fitted_scale == pytest.approx(standing.fitted_scale, rel=0.05)

    # ...and the foot nobody can see lands where it lands when it IS seen.
    assert seated.segment_lengths["left_foot"] == pytest.approx(
        standing.segment_lengths["left_foot"], rel=0.05
    )
    assert seated.segment_lengths["left_upper_leg"] == pytest.approx(
        standing.segment_lengths["left_upper_leg"], rel=0.05
    )


def test_the_seated_fit_is_driven_by_the_arms() -> None:
    """Naming the mechanism, so a future change that breaks it fails here loudly."""
    _, _ = _skeleton_and_voting_segments()
    seated = _fit(_seated_keypoints())

    assert seated.voting_segment_names <= {
        "left_upper_arm",
        "right_upper_arm",
        "left_lower_arm",
        "right_lower_arm",
    }, (
        "with the legs hidden and every hand keypoint absent, the only segments left "
        f"measuring the subject should be the arms - got {sorted(seated.voting_segment_names)}"
    )
