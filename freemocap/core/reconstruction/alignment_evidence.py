"""Connect tracker landmark evidence to Forge's model-owned alignment estimators."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from skellyforge.core.biomechanics.alignment_definition import AlignmentDefinition
from skellyforge.core.biomechanics.body_alignment import BodyReferenceTrack
from skellyforge.core.biomechanics.ground_alignment import FootContactTrack
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.hydration import (
    DegenerateObservations, MissingLandmarkObservations, hydrate_segment,
)
from skellyforge.core.skeleton.skeleton_pose import SegmentPose

from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle


@dataclass(frozen=True, slots=True, kw_only=True)
class AlignmentEvidenceRequest:
    """One model instance, actual timestamps, and measured reconstruction quality.

    Positions are Blender-convention millimeters. Quality is in [0,1], with zero
    for absent/rejected evidence. Single-camera planar results are not 3D evidence.
    """

    bundle: TrackedSkeletonBundle
    definition: AlignmentDefinition
    timestamps_seconds: NDArray[np.float64]
    keypoint_names: tuple[str, ...]
    positions: NDArray[np.float64]
    quality: NDArray[np.float64]
    minimum_quality: float

    def __post_init__(self) -> None:
        count = len(self.timestamps_seconds)
        if self.positions.shape != (count, len(self.keypoint_names), 3):
            raise ValueError("Alignment positions must match timestamp and keypoint axes")
        if self.quality.shape != self.positions.shape[:2]:
            raise ValueError("Alignment quality must match the position axes")
        if not np.isfinite(self.quality).all() or np.any((self.quality < 0) | (self.quality > 1)):
            raise ValueError("Alignment quality must be finite and in [0,1]")
        if not np.isfinite(self.timestamps_seconds).all() or np.any(np.diff(self.timestamps_seconds) <= 0):
            raise ValueError("Alignment timestamps must be finite and increase strictly")
        if len(set(self.keypoint_names)) != len(self.keypoint_names):
            raise ValueError("Alignment keypoint names must be unique")
        if not 0 < self.minimum_quality <= 1:
            raise ValueError("Alignment minimum_quality must be in (0,1]")
        if not np.isfinite(self.positions[self.quality > 0]).all():
            raise ValueError("Positive-quality alignment positions must be finite")
        for region in self.definition.body_regions:
            if self.bundle.skeleton.segments.get(region.name) is not region:
                raise ValueError("Alignment regions must belong to the bundle's model")
        for contact in self.definition.foot_contacts:
            if self.bundle.skeleton.landmarks.get(contact.name) is not contact:
                raise ValueError("Alignment contacts must belong to the bundle's model")


@dataclass(frozen=True, slots=True, kw_only=True)
class AlignmentEvidence:
    body_tracks: tuple[BodyReferenceTrack, ...]
    foot_contacts: tuple[FootContactTrack, ...]

    @classmethod
    def collect(cls, *, request: AlignmentEvidenceRequest) -> "AlignmentEvidence":
        count = len(request.timestamps_seconds)
        poses: dict[str, list[SegmentPose | None]] = {
            region.name: [] for region in request.definition.body_regions
        }
        region_quality = {name: np.zeros(count) for name in poses}
        contact_positions = {
            contact.name: np.full((count, 3), np.nan) for contact in request.definition.foot_contacts
        }
        contact_quality = {name: np.zeros(count) for name in contact_positions}
        for frame_index in range(count):
            indices = np.flatnonzero(request.quality[frame_index] >= request.minimum_quality)
            measured = request.bundle.landmark_mapping.apply_with_quality(
                tracker_positions={request.keypoint_names[index]: request.positions[frame_index, index] for index in indices},
                tracker_quality={request.keypoint_names[index]: float(request.quality[frame_index, index]) for index in indices},
            )
            observed = {name: Point.from_array(values=value) for name, value in measured.positions.items()}
            for region in request.definition.body_regions:
                try:
                    pose = hydrate_segment(segment=region, observed=observed)
                except (MissingLandmarkObservations, DegenerateObservations):
                    # An unobservable orientation contributes an explicit missing sample.
                    pose = None
                poses[region.name].append(pose)
                scores = [measured.quality[name] for name in region.landmarks if name in measured.quality]
                if scores:
                    region_quality[region.name][frame_index] = min(scores)
            for name in contact_positions:
                if name in measured.positions:
                    contact_positions[name][frame_index] = measured.positions[name]
                    contact_quality[name][frame_index] = measured.quality[name]
        return cls(
            body_tracks=tuple(BodyReferenceTrack.from_segment_poses(
                segment_name=name, poses=tuple(values), rest_pose=request.bundle.rest_pose,
                timestamps_seconds=request.timestamps_seconds, quality=region_quality[name],
            ) for name, values in poses.items()),
            foot_contacts=tuple(FootContactTrack(
                landmark_name=name, timestamps_seconds=request.timestamps_seconds.copy(),
                positions=values, quality=contact_quality[name],
            ) for name, values in contact_positions.items()),
        )
