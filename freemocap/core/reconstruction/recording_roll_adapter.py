"""Explicit boundary to Forge's current object-only temporal roll resolver.

This is the remaining array/object conversion in recording reconstruction. The
standalone Forge API must gain an array operation before this adapter can go;
core deliberately keeps the live solver's numerical and temporal behavior.
"""
from dataclasses import replace
import numpy as np
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.hydration_batch import HydratedPoseBatch
from skellyforge.core.skeleton.pose.roll_resolution import ContinuousRollResolver
from skellyforge.core.skeleton.skeleton_pose import SkeletonPose, SegmentPose


def resolve_recording_roll(*, poses: HydratedPoseBatch, segment_names: tuple[str, ...],
                           resolver: ContinuousRollResolver | None, empty_frames: np.ndarray) -> HydratedPoseBatch:
    if resolver is None:
        return poses
    rotations = poses.orientations.copy()
    solutions = poses.solutions.copy()
    present = poses.segment_present
    for frame_index in range(len(rotations)):
        if empty_frames[frame_index]:
            resolver.reset()
        columns = np.flatnonzero(present[frame_index])
        if not len(columns):
            continue
        pose = SkeletonPose(segment_poses={segment_names[column]: SegmentPose(
            segment_name=segment_names[column], origin=Point.from_array(values=poses.origins[frame_index, column]),
            orientation=RotationQuaternion.from_array(array=poses.orientations[frame_index, column]),
            scale_estimate=float(poses.scale_estimates[frame_index, column]),
            solved_by=poses.solutions[frame_index, column]) for column in columns})
        resolved = resolver.resolve_pose(pose=pose)
        for column in columns:
            segment = resolved.segment_poses[segment_names[column]]
            rotations[frame_index, column] = segment.orientation.as_array()
            solutions[frame_index, column] = segment.solved_by
    return replace(poses, orientations=rotations, solutions=solutions)
