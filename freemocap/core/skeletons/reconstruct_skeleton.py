"""Reconstruct ONE skeleton from one frame's keypoints.

Everything the realtime loop does per tracked skeleton, in one place: map keypoints to
landmarks, hydrate, resolve roll, fit scale, size every segment, and place the centre of
mass. The aggregator calls it once per skeleton and collects the results.

Pulled out of the aggregator rather than inlined there because "do this for each tracked
skeleton" should be a loop over a named thing, not fifty lines that a reader has to check
for hidden assumptions about which skeleton they refer to.

Cross-frame state lives in the caller-owned `SkeletonReconstructionState`, never in the
bundle: this is a pure function of one frame given that state, which is what makes it
testable without a pipeline AND what lets the posthoc driver call the very same function
with a whole-recording scale fit instead of a rolling one.
"""
from __future__ import annotations

import numpy as np
from skellyforge.core.biomechanics.center_of_mass import (
    compute_segment_coms,
    landmark_world_positions,
)
from skellyforge.core.biomechanics.composite_inertia import whole_body_center_of_mass
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.hydration import hydrate_skeleton
from skellyforge.core.skeleton.pose.model_scale_fitting import ModelScaleFit

from freemocap.core.skeletons.reconstruction_state import SkeletonReconstructionState
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle


def reconstruct_skeleton(
    *,
    bundle: TrackedSkeletonBundle,
    state: SkeletonReconstructionState,
    filtered_keypoints: dict[str, np.ndarray],
    compute_center_of_mass: bool,
) -> SkeletonReconstruction | None:
    """This skeleton's reconstruction for one frame, or `None` if it did not hydrate.

    Args:
        bundle: the skeleton being reconstructed — what it IS, authored once.
        state: what reconstructing it has accumulated over this take — the scale source and
            the roll carry. Mutated here; owned by the caller.
        filtered_keypoints: every detector's keypoints this frame, already smoothed and
            gated. The bundle's mapping takes only the ones it recognizes, so one flat
            dict feeds every skeleton.
        compute_center_of_mass: whether to place the centre of mass this frame.

    Returns:
        The reconstruction, or `None` when nothing of this skeleton was visible - which is
        an absent model this frame, not an empty one.
    """
    mapped_landmarks = bundle.landmark_mapping.apply(tracker_positions=filtered_keypoints)
    if not mapped_landmarks:
        return None
    observed = {
        name: Point.from_array(values=position)
        for name, position in mapped_landmarks.items()
    }
    hydrated_pose = hydrate_skeleton(
        skeleton=bundle.skeleton, observed=observed, require_all=False
    )
    if not hydrated_pose.segment_poses:
        return None
    # A skeleton that measures its own roll (every segment fully specified, as a rigid
    # marked object is) opted out of roll resolution, and applying a continuity convention
    # to it would invent state where there is a measurement.
    resolved_pose = (
        state.roll_resolver.resolve_pose(pose=hydrated_pose)
        if state.roll_resolver is not None
        else hydrated_pose
    )

    landmarks = dict(mapped_landmarks)
    for segment in bundle.skeleton.segments.values():
        segment_pose = resolved_pose.segment_poses.get(segment.name)
        if segment_pose is None:
            # Partial hydration: a segment whose landmarks were not observed this frame is
            # absent from the pose, so its origin is absent too rather than stale.
            continue
        landmarks[segment.frame_definition.origin_point_name] = segment_pose.origin.array

    state.scale_source.observe_pose(pose=resolved_pose)
    scale_fit: ModelScaleFit | None = (
        state.scale_source.current_fit()
        if state.scale_source.has_model_scale
        else None
    )

    reconstruction = SkeletonReconstruction(
        model_id=bundle.model_id,
        landmarks=landmarks,
        segment_rotations_world={
            name: segment_pose.orientation.as_array()
            for name, segment_pose in resolved_pose.segment_poses.items()
        },
        segment_rotations_local={
            name: rotation.as_array()
            for name, rotation in resolved_pose.parent_relative_orientations(parents=bundle.rest_pose.parents).items()
        },
        segment_lengths=dict(scale_fit.segment_lengths) if scale_fit else {},
        fitted_scale_mm=scale_fit.fitted_scale if scale_fit else None,
        joint_angles=(
            {
                joint_name: joint_pose.angles
                for joint_name, joint_pose in bundle.skeleton.compute_joint_poses(
                    pose=resolved_pose
                ).items()
            }
            if bundle.skeleton.joints
            else None
        ),
    )

    if compute_center_of_mass and scale_fit is not None:
        # Landmark world positions need the fitted scale: local positions are fractions of
        # the skeleton's reference unit, so without it every landmark collapses onto its
        # segment's origin and the centre of mass becomes an average of joint centres.
        world = landmark_world_positions(
            skeleton=bundle.skeleton,
            pose=resolved_pose,
            segment_scales=scale_fit.segment_scales,
        )
        reconstruction.center_of_mass = whole_body_center_of_mass(
            segment_coms=compute_segment_coms(
                definitions=bundle.center_of_mass_definitions, world=world
            ),
            segment_masses=bundle.segment_masses,
        )
    return reconstruction

