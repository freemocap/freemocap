"""One tracked skeleton, and everything the pipeline needs to reconstruct it.

A session tracks SEVERAL skeletons - a person and a charuco board are two - and may track
several INSTANCES of one (two people). Every stage that used to hold "the standard human"
holds a tuple of these instead, and loops.

The bundle says WHAT is being reconstructed — the definition, its rest pose, the mapping
that feeds it, its mass model. All of that is authored once and is identical for every run
tracking the same thing, so the bundle is genuinely immutable.

What accumulates over a take — the scale fit and the roll carry — lives in
`SkeletonReconstructionState` beside it, not in here. That separation is what lets one
`reconstruct_skeleton` serve both the realtime and posthoc pipelines.

Bundles are still rebuilt when the detector changes: a different detector measures
different landmarks, so the mapping changes with it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from skellyforge.core.biomechanics.center_of_mass import CenterOfMassDefinitions
from skellyforge.core.skeleton.pose.rest_pose import RestPose
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition


@runtime_checkable
class KeypointToLandmarkMapping(Protocol):
    """Turns one frame of tracker keypoints into this skeleton's landmark observations.

    A Protocol rather than a union of the two implementations that exist today: a mapping
    is a role, and enumerating today's occupants of a role is how a union ends up being
    edited every time a third one appears. A pass-through board mapping and a
    weighted/offset human mapping both satisfy this without either knowing about the other.
    """

    def apply(
        self, tracker_positions: dict[str, np.ndarray]
    ) -> dict[str, np.ndarray]:
        """The landmark observations this frame's keypoints produce.

        Named `apply` to match skellytracker's `TrackerMapping`, which is the external
        contract here - a mapping loaded straight from a YAML satisfies this as-is, with
        no adapter whose only job would be to rename a method.
        """
        ...

    @property
    def directly_measured_landmark_names(self) -> frozenset[str]:
        """The landmarks this mapping MEASURES rather than constructs from the template.

        Only segments built entirely from these may set the skeleton's fitted scale.
        """
        ...


@dataclass(frozen=True, slots=True)
class TrackedSkeletonBundle:
    """One skeleton the pipeline is reconstructing this run.

    Attributes:
        model_id: what this skeleton is called on the wire. Instances reference it.
        detector_type: the tracker feeding it ("rtmpose", "charuco"). A session runs
            several, and each skeleton is fed by exactly one, so the pairing lives here
            rather than as a single value on the stream context.
        tracker_keypoint_names: every keypoint that detector can emit, in wire order.
        skeleton: the definition being hydrated.
        rest_pose: its reference pose - authored for the human, defaulted for a rigid
            object that has nothing to author.
        landmark_mapping: keypoints in, landmark observations out.
        center_of_mass_definitions: how this skeleton's mass is distributed. EVERY skeleton
            has these - a skeleton that declares no mass model gets the unweighted mean of
            each segment's landmarks - so this is never absent.
        segment_masses: mass per segment, in the units the caller works in.
        scale_reference_name: what this skeleton's `1.0` means ("body_height",
            "square_length"), so a consumer can label the fitted number without knowing
            which skeleton it came from.
    """

    model_id: str
    detector_type: str
    tracker_keypoint_names: tuple[str, ...]
    skeleton: SkeletonDefinition
    rest_pose: RestPose
    landmark_mapping: KeypointToLandmarkMapping
    center_of_mass_definitions: CenterOfMassDefinitions
    segment_masses: dict[str, float]
    scale_reference_name: str
