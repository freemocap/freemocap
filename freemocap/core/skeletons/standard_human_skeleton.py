"""The standard human, bundled for a run.

One of (currently two) skeleton builders. Each one answers the same question - "what am I
tracking, and with what?" - so the pipeline can hold a tuple of them and never ask which
is which.
"""
from __future__ import annotations

from skellyforge.core.biomechanics.anthropometric_parameters import AnthropometricParameters
from skellyforge.core.biomechanics.center_of_mass import CenterOfMassDefinitions
from skellyforge.core.skeleton.pose.model_scale_fitting import (
    StreamingModelScaleFitter,
    scale_voting_segment_names,
)
from skellyforge.core.skeleton.pose.rest_pose import RestPose
from skellyforge.core.skeleton.pose.roll_resolution import ContinuousRollResolver
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition

from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.tasks.mocap.tracker_mappings import (
    load_standard_human_mapping,
    tracker_keypoint_names,
)

STANDARD_HUMAN_MODEL_ID: str = "standard_human"
BODY_HEIGHT_SCALE_REFERENCE: str = "body_height"
ASSUMED_BODY_MASS_KG: float = 70.0
"""Until a subject's mass is asked for, de Leva's fractions need something to scale.

Only the RATIOS between segment masses affect the centre of mass, so this cancels out of
the CoM entirely; it matters for inertia, which is why it is named rather than inlined."""


def build_standard_human_bundle(*, detector_type: str) -> TrackedSkeletonBundle:
    """The human this run is tracking, wired to the detector that feeds it.

    Rebuilt when the detector changes: a different detector measures different landmarks,
    so which segments may set the fitted scale changes with it, and the readings taken
    through the old naming convention should not carry over.
    """
    skeleton = SkeletonDefinition.from_default_yaml()
    mapping = load_standard_human_mapping(detector_type)
    # The human declares a de Leva mass model, so its weighted sums override the
    # unweighted-mean default every skeleton would otherwise get.
    com_definitions = CenterOfMassDefinitions.from_default_yaml()
    com_definitions.validate_against(skeleton=skeleton)
    anthropometric = AnthropometricParameters.from_default_yaml()
    segment_masses: dict[str, float] = {}
    for definition in com_definitions.definitions.values():
        mass = anthropometric.get(name=definition.name).mass_fraction * ASSUMED_BODY_MASS_KG
        for full_name, _side in definition.side_entries:
            segment_masses[full_name] = mass

    return TrackedSkeletonBundle(
        model_id=STANDARD_HUMAN_MODEL_ID,
        detector_type=detector_type,
        tracker_keypoint_names=tuple(tracker_keypoint_names(detector_type)),
        skeleton=skeleton,
        rest_pose=RestPose.from_default_yaml(skeleton=skeleton),
        landmark_mapping=mapping,
        center_of_mass_definitions=com_definitions,
        segment_masses=segment_masses,
        scale_reference_name=BODY_HEIGHT_SCALE_REFERENCE,
    )
