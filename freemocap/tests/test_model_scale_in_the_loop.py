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
    DEFAULT_SCALE_WINDOW_FRAMES,
    StreamingModelScaleFitter,
    scale_voting_segment_names,
)
from skellyforge.core.skeleton.pose.hydration import hydrate_skeleton
from skellyforge.core.skeleton.pose.roll_resolution import ContinuousRollResolver
from skellyforge.core.skeleton.pose.rest_pose import RestPose
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


def _fit_sequence(frames: list[dict[str, np.ndarray]]) -> list[ModelScaleFit]:
    """Keep the mapping, roll resolver, and scale history across observed frames."""
    skeleton, voting = _skeleton_and_voting_segments()
    mapping = load_standard_human_mapping("rtmpose")
    resolver = ContinuousRollResolver.for_skeleton(
        skeleton=skeleton,
        rest_relative_orientations=RestPose.from_default_yaml(skeleton=skeleton).relative_orientations,
    )
    fitter = StreamingModelScaleFitter(skeleton=skeleton, voting_segment_names=voting)
    fits = []
    for keypoints in frames:
        observed = {name: Point.from_array(values=position)
                    for name, position in mapping.apply(tracker_positions=keypoints).items()}
        pose = resolver.resolve_pose(pose=hydrate_skeleton(skeleton=skeleton, observed=observed, require_all=False))
        fitter.observe_pose(pose=pose)
        fits.append(fitter.current_fit())
    return fits


def _fit(keypoints: dict[str, np.ndarray]) -> ModelScaleFit:
    return _fit_sequence([keypoints])[0]


def test_only_measured_landmarks_earn_a_vote_on_the_subjects_height() -> None:
    """The mapping's constructed landmarks must not vote on how big the subject is."""
    skeleton, voting = _skeleton_and_voting_segments()

    # Limb and axial segments with measured endpoints can vote on scale.
    for name in (
        "left_upper_leg",
        "right_upper_leg",
        "left_lower_leg",
        "right_lower_leg",
        "left_upper_arm",
        "right_upper_arm",
        "left_lower_arm",
        "right_lower_arm",
        "sacrolumbar",
        "cervical_spine",
    ):
        assert name in voting, f"{name} is measured end to end and should vote"

    # Segments requiring anatomical offsets must not vote with constructed geometry.
    for name in ("thoracic", "left_clavicle"):
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


def test_partial_visibility_cold_start_sizes_unobserved_segments_from_visible_evidence() -> None:
    """A fresh partial view estimates plausible proportions without invented leg measurements.

    This subject differs from the template. Different visible limb sets need not
    infer identical stature; exact recovery is tested with proportional geometry
    in SkellyForge's test_model_scale_fitting.py.
    """
    seated = _fit(_seated_keypoints())
    skeleton, _ = _skeleton_and_voting_segments()
    low, high = _PLAUSIBLE_HEIGHT_RANGE_MM
    assert low < seated.fitted_scale < high
    assert seated.voting_segment_names
    for name in ('left_foot', 'right_foot', 'left_lower_leg', 'right_lower_leg'):
        assert name not in seated.measured_segment_names
        proportion = skeleton.segments[name].length
        assert seated.segment_lengths[name] == pytest.approx(proportion * seated.fitted_scale)
        assert proportion * low < seated.segment_lengths[name] < proportion * high


def test_established_subject_scale_remains_stable_through_occlusion_and_return() -> None:
    """An established observation window survives a longer occlusion and reappearance."""
    window = DEFAULT_SCALE_WINDOW_FRAMES
    standing, seated = _standing_keypoints(), _seated_keypoints()
    fits = _fit_sequence([standing] * window + [seated] * (2 * window) + [standing] * window)
    baseline = fits[window - 1]
    assert not any(any(hidden in name for hidden in _BELOW_THE_DESK) for name in seated)
    for fit in fits[window:]:
        assert fit.fitted_scale == pytest.approx(baseline.fitted_scale, rel=0.05)
        for name in ('left_foot', 'right_foot', 'left_upper_leg', 'right_upper_leg'):
            assert fit.segment_lengths[name] == pytest.approx(baseline.segment_lengths[name], rel=0.05)


def test_the_seated_fit_uses_visible_measured_segments() -> None:
    """Visible arms and axial spans supply evidence; hidden limbs do not."""
    _, _ = _skeleton_and_voting_segments()
    seated = _fit(_seated_keypoints())

    assert seated.voting_segment_names <= {
        "left_upper_arm",
        "right_upper_arm",
        "left_lower_arm",
        "right_lower_arm",
        "sacrolumbar",
        "cervical_spine",
    }, (
        "With legs and hands absent, only visible arms and axial spans may vote: "
        f"got {sorted(seated.voting_segment_names)}"
    )
